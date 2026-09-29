from PIL import Image, ImageChops
img1 = Image.open("workspace/uhid_before.png")
img2 = Image.open("workspace/uhid_after.png")
diff = ImageChops.difference(img1, img2)
bbox = diff.getbbox()
print(f"before extrema: {img1.getextrema()}")
print(f"after extrema:  {img2.getextrema()}")
print(f"diff bbox: {bbox}")
if bbox is None:
    print("两张截图完全相同 - 点击未生效")
else:
    print(f"差异区域: {bbox}")
    diff.save("workspace/uhid_diff.png")
