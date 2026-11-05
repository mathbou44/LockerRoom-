"""5 nov 2026 : une photo examinee est allegee (2400 px, JPEG 85), meme nom ; une petite photo ou tournee (EXIF) : rien."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import photos_cartes
from PIL import Image
import numpy as np

d = tempfile.mkdtemp()
grande = os.path.join(d, "a" * 16 + ".jpg")
Image.fromarray((np.random.RandomState(1).rand(4800, 3600, 3) * 255).astype("uint8")).save(grande, quality=95)
avant = os.path.getsize(grande)
petite = os.path.join(d, "b" * 16 + ".jpg")
Image.new("RGB", (800, 600), (20, 30, 40)).save(petite, quality=90)
tournee = os.path.join(d, "c" * 16 + ".jpg")
im = Image.fromarray((np.random.RandomState(2).rand(4000, 3000, 3) * 255).astype("uint8")); ex = im.getexif(); ex[0x0112] = 6
im.save(tournee, quality=95, exif=ex)
t_avant = os.path.getsize(tournee)
g = photos_cartes.alleger([grande, petite, tournee, None, os.path.join(d, "absent.jpg")])
assert g > 0 and os.path.getsize(grande) < avant, (g, avant)
with Image.open(grande) as x:
    assert max(x.size) == 2400 and abs(x.size[0] / x.size[1] - 0.75) < 0.01, x.size
assert os.path.getsize(tournee) == t_avant
assert not [f for f in os.listdir(d) if f.endswith(".allege")]
print("ALLEGER OK")
