import io
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image, PngImagePlugin
import pytest
from media_service.pipeline import ImageError, inspect_image, process


@pytest.mark.parametrize('case,code', [('mismatch','invalid_document'),('truncated','invalid_document'),
    ('huge','image_dimensions'),('side','image_dimensions'),('animated','image_animation'),('mode','image_color_mode')])
def test_image_validation_before_upstream(tmp_path,case,code):
    p=tmp_path/'image.png'
    if case=='mismatch': Image.new('RGB',(4,4)).save(p,'JPEG')
    elif case=='truncated': p.write_bytes(b'\x89PNG\r\n\x1a\n')
    elif case=='huge': Image.new('RGB',(3000,3000)).save(p)
    elif case=='side': Image.new('RGB',(8193,1)).save(p)
    elif case=='animated': Image.new('RGB',(4,4),'red').save(p,save_all=True,append_images=[Image.new('RGB',(4,4),'blue')],duration=100)
    else: Image.new('I;16',(4,4)).save(p)
    with pytest.raises(ImageError) as caught: inspect_image(p,p.name)
    assert caught.value.code==code


@pytest.mark.parametrize('suffix', ['png','jpg','webp'])
def test_upstream_is_called_and_orientation_metadata_alpha_preserved(tmp_path,monkeypatch,suffix):
    import remove_ai_watermarks
    image=Image.new('RGBA',(7,5),(20,40,60,120))
    if suffix=='jpg': image=image.convert('RGB')
    tags=Image.Exif();tags[274]=6;tags[315]='Private creator'
    source=tmp_path/('source.'+suffix); image.save(source,exif=tags)
    calls=[]
    def fake(path,**kwargs):
        calls.append((path,kwargs))
        with Image.open(path) as im: array=np.array(im.convert('RGB'))[:,:,::-1].copy()
        return SimpleNamespace(image=array,marks=(),status='no_watermark')
    monkeypatch.setattr(remove_ai_watermarks,'remove_visible_detailed',fake)
    destination=tmp_path/'cleaned.png';result=process(source,source.name,destination)
    assert calls==[(source,{'backend':'cv2','sensitivity':'auto','strip_metadata':False})]
    with Image.open(destination) as out:
        assert out.size==(5,7) and not out.getexif()
        assert set(out.info)=={'icc_profile'}
        assert out.mode=='RGBA'
        assert out.getchannel('A').getextrema()==((255,255) if suffix=='jpg' else (120,120))
    assert result['metadata_removed'] is True


def test_real_upstream_clean_image_does_not_change_pixels(tmp_path):
    source=tmp_path/'source.png'; Image.new('RGBA',(96,80),(10,80,20,170)).save(source)
    dest=tmp_path/'result.png';result=process(source,source.name,dest)
    assert result['visual_status']=='no_watermark'
    with Image.open(source) as a,Image.open(dest) as b: assert a.tobytes()==b.tobytes()


@pytest.mark.parametrize('visual', ['partial','unvalidated','cleaned'])
def test_visual_status_is_retained(tmp_path,monkeypatch,visual):
    import remove_ai_watermarks
    source=tmp_path/'input.png';Image.new('RGB',(80,80)).save(source)
    mark=SimpleNamespace(key='gemini',label='Gemini',status=visual,backend='cv2')
    monkeypatch.setattr(remove_ai_watermarks,'remove_visible_detailed',lambda *a,**k:SimpleNamespace(image=np.zeros((80,80,3),dtype=np.uint8),marks=(mark,),status=visual))
    result=process(source,source.name,tmp_path/'out.png')
    assert result['visual_status']==visual
    assert result['status']==('cleaned' if visual=='cleaned' else 'partial')


def test_two_registered_marks_are_cleaned_in_one_real_pass(tmp_path):
    root=Path(__file__).resolve().parents[2]/'tests/fixtures/images'
    with Image.open(root/'supported-gemini.png') as a,Image.open(root/'supported-microsoft.png') as b:
        combined=a.convert('RGB');combined.paste(b.crop((0,0,b.width,200)),(0,0))
    source=tmp_path/'combined.png';combined.save(source)
    result=process(source,source.name,tmp_path/'out.png')
    assert {'gemini','microsoft'}.issubset({m['key'] for m in result['marks']})
    assert result['visual_status']=='cleaned'


def test_output_limit_is_enforced_before_return(tmp_path,monkeypatch):
    import media_service.pipeline as pipeline
    source=tmp_path/'source.png';Image.new('RGB',(80,80),'green').save(source)
    monkeypatch.setattr(pipeline,'MAX_OUTPUT',100)
    with pytest.raises(ImageError) as caught: process(source,source.name,tmp_path/'out.png')
    assert caught.value.code=='output_too_large'
