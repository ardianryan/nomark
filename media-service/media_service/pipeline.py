"""Bounded adapter for the pinned remove-ai-watermarks public API."""
import io
from pathlib import Path
import warnings

from PIL import Image, ImageCms, ImageOps

MAX_INPUT = 20 * 1024 * 1024
MAX_OUTPUT = 40 * 1024 * 1024
MAX_PIXELS = 8_000_000
MAX_SIDE = 8192
FORMATS = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG', '.webp': 'WEBP'}
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class ImageError(Exception):
    def __init__(self, code, status=422):
        self.code, self.status = code, status
        super().__init__(code)


def validate_name(name):
    if (not isinstance(name, str) or not 0 < len(name) <= 240 or
            any(c in name for c in ('/', '\\')) or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise ImageError('invalid_name', 400)
    if Path(name).suffix.lower() not in FORMATS:
        raise ImageError('unsupported_format', 415)
    return name


def inspect_image(source, name):
    validate_name(name)
    size = source.stat().st_size
    if not size:
        raise ImageError('empty_file', 400)
    if size > MAX_INPUT:
        raise ImageError('file_too_large', 413)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(source) as image:
                if image.format != FORMATS[Path(name).suffix.lower()]:
                    raise ImageError('invalid_document')
                w, h = image.size
                if w < 1 or h < 1 or w * h > MAX_PIXELS or max(w, h) > MAX_SIDE:
                    raise ImageError('image_dimensions', 413)
                if getattr(image, 'n_frames', 1) != 1:
                    raise ImageError('image_animation')
                if image.mode not in ('RGB', 'RGBA', 'L', 'LA', 'P'):
                    raise ImageError('image_color_mode')
                if image.format == 'PNG':
                    with source.open('rb') as stream:
                        header = stream.read(26)
                    if len(header) < 26 or header[24] > 8:
                        raise ImageError('image_color_mode')
                orientation = image.getexif().get(274, 1)
                if orientation not in range(1, 9):
                    raise ImageError('invalid_document')
                icc = image.info.get('icc_profile')
                if icc is not None and (not isinstance(icc, bytes) or len(icc) > 1024 * 1024):
                    raise ImageError('image_color_mode')
                had_metadata = bool(image.getexif() or any(k not in {'transparency', 'duration', 'loop'} for k in image.info))
            with Image.open(source) as verify_image:
                verify_image.verify()
            with Image.open(source) as image:
                image.load()
                rgba = image.convert('RGBA')
                rgba.info.clear()
        return rgba, orientation, icc, had_metadata
    except ImageError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImageError('image_dimensions', 413) from None
    except Exception:
        raise ImageError('invalid_document') from None


def normalized(image, orientation, icc):
    alpha = image.getchannel('A')
    rgb = image.convert('RGB')
    if icc:
        try:
            rgb = ImageCms.profileToProfile(rgb, ImageCms.ImageCmsProfile(io.BytesIO(icc)),
                                           ImageCms.createProfile('sRGB'), outputMode='RGB')
        except Exception:
            raise ImageError('image_color_mode') from None
    result = rgb.convert('RGBA')
    result.putalpha(alpha)
    result.getexif()[274] = orientation
    result = ImageOps.exif_transpose(result)
    result.info.clear()
    return result


def process(source, name, destination):
    import cv2
    import numpy as np
    from remove_ai_watermarks import remove_visible_detailed

    cv2.setNumThreads(1)
    original, orientation, icc, metadata = inspect_image(source, name)
    # Pass the original path so upstream can use its local provenance evidence.
    report = remove_visible_detailed(source, backend='cv2', sensitivity='auto', strip_metadata=False)
    if report.image.dtype != np.uint8 or report.image.shape != (original.height, original.width, 3):
        raise ImageError('processing_failed')
    rgb = Image.fromarray(cv2.cvtColor(report.image, cv2.COLOR_BGR2RGB)).convert('RGBA')
    rgb.putalpha(original.getchannel('A'))
    output = normalized(rgb, orientation, icc)
    # Save a new raster with no user-controlled EXIF/text chunks. sRGB is explicit.
    srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    output.save(destination, format='PNG', icc_profile=srgb)
    if destination.stat().st_size > MAX_OUTPUT:
        raise ImageError('output_too_large', 413)
    with Image.open(destination) as check:
        check.load()
        if check.format != 'PNG' or check.size != output.size or check.mode != 'RGBA' or check.getexif():
            raise ImageError('processing_failed')
        if check.getchannel('A').tobytes() != output.getchannel('A').tobytes():
            raise ImageError('processing_failed')
        if set(check.info) - {'icc_profile'}:
            raise ImageError('processing_failed')
    marks = []
    for mark in report.marks:
        if len(marks) == 64:
            raise ImageError('processing_failed')
        if mark.status not in ('cleaned', 'partial', 'unvalidated') or mark.backend != 'cv2':
            raise ImageError('processing_failed')
        marks.append({'key': mark.key, 'label': mark.label, 'status': mark.status})
    if report.status not in ('no_watermark', 'cleaned', 'partial', 'unvalidated'):
        raise ImageError('processing_failed')
    return {'visual_status': report.status, 'marks': marks,
            'width': output.width, 'height': output.height,
            'metadata_removed': metadata, 'normalized': True,
            'status': 'partial' if report.status in ('partial', 'unvalidated') else
                      'cleaned' if report.marks or metadata else 'unchanged'}
