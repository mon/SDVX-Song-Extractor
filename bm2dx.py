import wave
import audioop
from io import BytesIO

from bytebuffer import ByteBuffer

class BM2DX(object):
    class Track(object):
        def __init__(self, buff):
            assert buff.get('4s') == b'2DX9'
            assert buff.get_u32() == 24
            wav_size = buff.get_u32()
            unk1 = buff.get_u16()
            self.id = buff.get_u16()
            unk2 = buff.get_u16()
            self.attenuation = buff.get_u16()
            self.loop_point = buff.get_u32()
            self.data = buff.get_bytes(wav_size)

        def __str__(self):
            return 'Track ID:{} attenuation:{} loop:{}'.format(self.id, self.attenuation, self.loop_point)


    def __init__(self, path):
        with open(path, 'rb') as f:
            self.contents = ByteBuffer(f.read(), endian = '<')
        self.name = self.contents.get('16s')
        self.header_size = self.contents.get_u32()
        self.filecount = self.contents.get_u32()
        self.contents.offset += 48 # random padding/flags/title bytes

        offsets = []
        for _ in range(self.filecount):
            offsets.append(self.contents.get_u32())

        self.tracks = []
        for off in offsets:
            self.contents.offset = off
            self.tracks.append(self.Track(self.contents))

    def __str__(self):
        ret = '2dx: "{}", {} track(s)'.format(self.name, len(self.tracks))
        for t in self.tracks:
            ret += '\n\t{}'.format(str(t))
        return ret
