import numpy as np
import argparse
import cv2
import os

from collections import namedtuple


class FilmCoverter:
    def __init__(self, infile, outfile, col_map, bg_colors):
        self.col_map = col_map
        self.infile = infile
        self.outfile = outfile
        self.bg_colors = bg_colors

    def convert(self, resolution, fourcc='DIVX', echo=True):
        self.cap = cv2.VideoCapture(self.infile)
        IN_HEIGHT = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        IN_WIDTH = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        FPS = self.cap.get(cv2.CAP_PROP_FPS)
        F_COUNT = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

        WIDTH, HEIGHT = resolution

        self.out = cv2.VideoWriter(self.outfile, cv2.VideoWriter_fourcc(*fourcc), FPS, (WIDTH, HEIGHT))

        outframe = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        cnt = 0
        canvas = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        canvas[:, :WIDTH // 2, 0] = np.ones((HEIGHT, WIDTH // 2), dtype=np.uint8) * self.bg_colors[0].blue
        canvas[:, :WIDTH // 2, 1] = np.ones((HEIGHT, WIDTH // 2), dtype=np.uint8) * self.bg_colors[0].green
        canvas[:, :WIDTH // 2, 2] = np.ones((HEIGHT, WIDTH // 2), dtype=np.uint8) * self.bg_colors[0].red
        canvas[:, WIDTH // 2:, 0] = np.ones((HEIGHT, WIDTH // 2), dtype=np.uint8) * self.bg_colors[1].blue
        canvas[:, WIDTH // 2:, 1] = np.ones((HEIGHT, WIDTH // 2), dtype=np.uint8) * self.bg_colors[1].green
        canvas[:, WIDTH // 2:, 2] = np.ones((HEIGHT, WIDTH // 2), dtype=np.uint8) * self.bg_colors[1].red

        cv2.imwrite('res.jpg', canvas)
        for i in range(WIDTH):
            outframe[:, i, :] = canvas[:, self.col_map[i], :] if self.col_map[i] != -1 else np.zeros((HEIGHT, 3), dtype=np.uint8)
        while cnt < 30 * FPS:
            self.out.write(outframe)
            cnt += 1
            if cnt % 30 == 0:
                self.__echo(cnt, 30 * FPS)

        print('\n----------------------------------')

        cnt = 0
        while True:
            ret, frame = self.cap.read()

            if ret:
                if IN_WIDTH != WIDTH:
                    frame = cv2.resize(frame, (WIDTH, HEIGHT), interpolation = cv2.INTER_CUBIC)
                for i in range(WIDTH):
                    outframe[:, i, :] = frame[:, self.col_map[i], :] if self.col_map[i] != -1 else np.zeros((HEIGHT, 3), dtype=np.uint8)
                self.out.write(outframe)
            else:
                break

            cnt += 1
            if echo and cnt % 30 == 0:
                self.__echo(cnt // 30, F_COUNT // 30)

        ffmpeg_cmd = 'ffmpeg -i %s -vn -f wav - | ffmpeg -i %s -f wav -i pipe: -c:v copy -c:a aac -strict experimental %s' % (self.infile, self.outfile, self.outfile)
        print('')
        print('ffmpeg cmd:', ffmpeg_cmd)

    def __echo(self, cnt, max_cnt):
        rotate = ['|', '/', '-', '\\']
        print('\r', end='')
        print('  ' + rotate[cnt % 4], end=' ')
        print('[' + ''.join(('=' if i < 40 * cnt / max_cnt else ' ' for i in range(40))) + ']', end='    ')
        print(str(int(cnt * 100 / max_cnt)) + '%', end='')


def col_mapper_generator(resolution, ppl, wpl):
    col_map = [-1, ] * (resolution[0] + int(ppl))
    padding_in_size = int((round(ppl) // 2 - wpl) // 2)
    padding_out_size = int(round(ppl) // 2) - padding_in_size - wpl
    half = resolution[0] // 2

    p = 0
    while int(p) + int(round(ppl)) < len(col_map):
        start_p = int(p)
        l_offset = start_p // 2
        r_offset = l_offset + half

        left_mask = [1, ] * padding_out_size + [-l_offset - wpl + 1 + i for i in range(wpl)] + [1, ] * padding_in_size
        right_mask = [1, ] * padding_in_size + [-r_offset - wpl + 1 + i for i in range(wpl)] + [1, ] * padding_out_size

        for m in left_mask:
            col_map[start_p] *= m
            start_p += 1

        start_p += int(round(ppl) % 2)

        for m in right_mask:
            col_map[start_p] *= m
            start_p += 1

        p += ppl

    return col_map


if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--resolution', type=int, nargs=2, required=True, help='Your screen resolution')
    parser.add_argument('-p', '--ppl', type=float, required=True, help='You ppl')
    parser.add_argument('-w', '--wpl', type=int, required=True, help='You wpl')
    parser.add_argument('-b', '--backgroud', type=str, nargs=2, required=False, default=('#00FF00', '#0000FF'), help='You backgroud color for calibration, the first one represents left eye calibration backgroud color. Please use the format like #FFFFFF')
    parser.add_argument('input', type=str, help='input filepath')
    parser.add_argument('output', type=str, help='output filepath')
    args = parser.parse_args()

    Color = namedtuple('Color', 'red green blue')
    try:
        left_bg = Color(*list(map(lambda x: int(x, 16), [args.backgroud[0][1:][i:i+2] for i in range(0, len(args.backgroud[0][1:]), 2)])))
        right_bg = Color(*list(map(lambda x: int(x, 16), [args.backgroud[1][1:][i:i+2] for i in range(0, len(args.backgroud[1][1:]), 2)])))
    except (ValueError, IndexError):
        print('Invalid backgroud color')
        exit(1)
    else:
        col_map = col_mapper_generator(args.resolution, args.ppl, args.wpl)
        fc = FilmCoverter(args.input, args.output, col_map, (left_bg, right_bg))
        fc.convert(args.resolution)
