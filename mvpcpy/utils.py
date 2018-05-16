from PIL import Image, ImageDraw, ImageFont

def mk_ppl_img(path, width, height, ppl):
    img = Image.new('RGB', (width, height))
    for x in (0, 2, width-3, width-1):
        for y in range(height):
            img.putpixel((x, y), (255, 255, 255))
    for y in (0, 2, height-3, height-1):
        for x in range(width):
            img.putpixel((x, y), (255, 255, 255))
    drawtop = 4
    drawheight = height - 8
    drawleft = 4
    drawwidth = width - 8
    lineheight = drawheight // 22
    gap = drawheight - 22 * lineheight
    font = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf', lineheight)
    draw = ImageDraw.Draw(img)
    draw.text((drawleft, drawtop), 'Grating.Science/ppl/%dx%d@%d.png' % (width, height, ppl), font=font, fill=(255, 255, 255))
    for i in range(21):
        draw.text((drawleft, drawtop+lineheight+gap+i*lineheight), '%04.1f' % (ppl-1+i*0.1), font=font, fill=(255, 255, 255))
        barsleft = drawleft + lineheight * 3
        barstop = drawtop+lineheight+gap+i*lineheight
        start = 0.0
        while start+barsleft < drawleft + drawwidth:
            for y in range(lineheight):
                img.putpixel((int(start)+barsleft, barstop+y), (0, 255, 0))
            start += ppl-1+i*0.1
    img.save(path)


def mk_wpl_img(path, width, height, ppl):
    img = Image.new('RGB', (width, height))
    for x in (0, 2, width-3, width-1):
        for y in range(height):
            img.putpixel((x, y), (255, 255, 255))
    for y in (0, 2, height-3, height-1):
        for x in range(width):
            img.putpixel((x, y), (255, 255, 255))
    drawtop = 4
    drawheight = height - 8
    drawleft = 4
    drawwidth = width - 8
    linecount = int(ppl // 2)
    lineheight = drawheight // (linecount+1)
    gap = drawheight - (linecount+1) * lineheight
    font = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf', lineheight)
    draw = ImageDraw.Draw(img)
    draw.text((drawleft, drawtop), 'wpl/%dx%d@%.1f.png' % (width, height, ppl), font=font, fill=(255, 255, 255))
    for i in range(linecount):
        draw.text((drawleft, drawtop+lineheight+gap+i*lineheight), '%d' % (i+1), font=font, fill=(255, 255, 255))
        barsleft = drawleft + lineheight * 2
        barstop = drawtop+lineheight+gap+i*lineheight
        start = 0.0
        while start+barsleft < drawleft + drawwidth:
            for w in range(i+1):
                for y in range(lineheight):
                    img.putpixel((int(start)+barsleft+w, barstop+y), (0, 255, 0))
            start += ppl
    img.save(path)