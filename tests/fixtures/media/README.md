# Synthetic media fixtures

Generated for NoMark tests: 8×8 solid RGB images and 0.1 seconds of silent PCM audio. Pillow generated the image containers; the Python standard library generated WAV. PNG, JPEG, WebP, GIF, and TIFF include a synthetic `stable diffusion` metadata label. WAV includes a synthetic LIST/INFO tag. There is no third-party content or trained model output.

The fixtures test metadata removal, decoded pixel equality in browsers, and unchanged WAV samples. The MP4, MP3, and FLAC structures built in `test_media.py` test parser boundaries and byte preservation; they are not complete playback fixtures.
