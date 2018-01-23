# `pip -r requirements.txt`
# Edit FOLDERS, OUT as desired

import sys
if sys.version_info < (3,0):
    raise NotImplementedError('Python 2 is not supported, please use Python 3')

from multiprocessing.dummy import Pool
import os, subprocess, errno
import tempfile
import shutil
from collections import OrderedDict

from bs4 import BeautifulSoup
from tqdm import tqdm
from PIL import Image
from ifstools import IFS

from bm2dx import BM2DX

# If you only want one format, change the unwanted ones to false
# the source wavs are lossy (ADPCM) so a FLAC is not created
PROCESS = {
    '320'  : False,
    'V0'   : True,
}

# the raw files are quite quiet. Normalise them?
AMPLIFY = True

# add as many as you need to get all deleted songs
# recommended: old releases first, as new versions may add new audio
FOLDERS = ["D:\\Users\\Will\\Rhythm\\Sound Voltex II -Infinite Infection-",
           "D:\\Users\\Will\\Rhythm\\Sound Voltex III -Gravity Wars- Final",
           "D:\\Users\\Will\\Rhythm\\Sound Voltex IV - Heavenly Haven",
]

#OUT = "Sound Voltex GST"
OUT = r"D:\Users\Will\Rhythm\SongExtractor\Sound Voltex IV Extracted Soundtrack"
ALBUM_NAME = "Sound Voltex Soundtrack"

LAME = r"D:\Users\Will\Rhythm\SongExtractor\lame.exe"
SOX = r"D:\Users\Will\Rhythm\SongExtractor\sox.exe"

# do any filtering here
def filter_func(songs):
    for id, song in list(songs.items()):
        if song.ver != 4:
            songs.pop(id)
        #pass

# can ignore below this line
# -----------------------------------------------------------------------------

if not os.path.isfile(LAME):
    raise OSError('lame encoder exe not found')
if not os.path.isfile(SOX):
    raise OSError('sox converter exe not found')

MAX_DIFF = 5 # NOV/ADV/EXH/INF/MXM

OUTV0 = os.path.join(OUT, OUT + ' (V0)')
OUT320 = os.path.join(OUT, OUT + ' (320)')

DB_PATH = "data/others/music_db.xml"
JACKET_PATH = "data/graphics/jk"
SONG_PATH = "data/sound"

TEMP = tempfile.gettempdir()

def quote(thing):
    return '"' + thing.replace('"', '\\"') + '"'

class Song(object):
    dx_versions = [
        '1n',
        '2a',
        '3e',
        '4i',
        '5m',
    ]

    diff_map = {
        'NOV' : 1,
        'ADV' : 2,
        'EXH' : 3,
        'INF' : 4,
        'MXM' : 5,
    }

    diff_strings = {v:k for k, v in diff_map.items()}

    def __init__(self, folder, all_2dx, all_jackets, xml):
        self.folder = folder
        self.all_2dx = all_2dx
        self.all_jackets = all_jackets

        self.name      = fixBrokenChars(xml.title_name.text)
        self.id        = int(xml['id'])
        self.ver       = int(xml.version.text)
        self.infVer    = int(xml.inf_ver.text) if xml.inf_ver else 0
        self.label     = xml.label.text
        self.asciiName = xml.ascii.text
        self.artist    = fixBrokenChars(xml.artist_name.text)
        self.minBpm    = int(xml.bpm_min.text) / 100.0
        self.maxBpm    = int(xml.bpm_max.text) / 100.0
        self.volume    = int(xml.volume.text) / 127.0

        self.find_2dx()
        self.find_jackets()

    @property
    def infname(self):
        return {2: 'INF', 3: 'GRV', 4: 'HVN'}.get(self.infVer, 'INF')

    def find_2dx(self):
        try:
            # standard
            filename = "{:03d}_{:04d}_{}".format(self.ver, int(self.label), self.asciiName)
        except ValueError:
            # booth
            filename = "{}_{}".format(self.label, self.asciiName)
        # because some songs are still annoying
        if not self.dx_test(filename):
            filename = "{:03d}_{:04d}_{}".format(self.ver, self.id, self.asciiName)

        self.dx = [
            self.dx_test(filename)
        ]
        for ver in self.dx_versions:
            ver_name = '{}_{}'.format(filename, ver)
            self.dx.append(self.dx_test(ver_name))

        if all(x is None for x in self.dx):
            raise KeyError('Song {} has no music files'.format(self.id))

    def find_jackets(self):
        jack_fmt = "jk_{:03d}_{:04d}_{}_b"
        self.jackets = []
        for i in range(MAX_DIFF):
            jack = jack_fmt.format(self.ver, self.id, i+1)
            self.jackets.append(self.jacket_test(jack))

        if all(x is None for x in self.jackets):
            raise KeyError('Song {} has no jacket files'.format(self.id))

    def dx_test(self, dx):
        dx += '.2dx'
        return dx if dx in self.all_2dx else None

    def jacket_test(self, jacket):
        jacket += '.ifs'
        return jacket if jacket in self.all_jackets else None

    def get_jacket(self, diff = None):
        if diff is None:
            diff = self.diff_map['EXH']

        diff -= 1
        if self.jackets[diff]:
            return self.jackets[diff]

        # go down until we find something, wrap if required
        test = list(range(diff, 0, -1)) + list(range(MAX_DIFF+1-diff, diff, -1))
        for t in test:
            t -= 1
            if self.jackets[t]:
                return self.jackets[t]

        return None

    def extract_jacket(self, diff = None):
        path = os.path.join(self.folder, JACKET_PATH, self.get_jacket(diff))
        ifs = IFS(path)
        textures = ifs.tree.folders['tex'].files.values()
        jacket = next(x for x in textures if x.name.endswith('.png'))
        dest = os.path.join(TEMP, jacket.name)
        with open(dest, 'wb') as f:
            f.write(jacket.load())
        return dest

    @property
    def sanitized(self):
        sanitized = self.name
        # strip bad chars that windows won't allow
        homoglyphs = {
            '\\' : '＼',
            '/' : '⁄',
            ':' : '։',
            '*' : '⁎',
            '?' : '？',
            '"' : "''",
            '<' : '‹',
            '>' : '›',
            '|' : 'ǀ',
        }
        for bad, good in homoglyphs.items():
            sanitized = sanitized.replace(bad, good)
        return sanitized

    def load_2dx(self, dx):
        return BM2DX(os.path.join(self.folder, SONG_PATH, dx)).tracks

    def _lame_enc(self, jacket, wav, mp3, quality):
        bpmStr = twoDecimals(self.minBpm)
        if self.minBpm != self.maxBpm:
            bpmStr += '-' + twoDecimals(self.maxBpm)

        run(LAME, ' '.join([
            quality,
            quote(wav),
            quote(mp3),
            '--tt', quote(self.name),
            '--ta', quote(self.artist),
            '--tl', quote(ALBUM_NAME),
            '--tn', quote(str(self.id)),
            '--tv', 'TPE2="Various Artists"',
            '--tv', 'TPOS=' + str(self.ver),
            '--tv', 'TBPM="' + bpmStr + '"',
            '--ti', quote(jacket),
        ]))

    def _convert(self, dx, diff = None):
        jacket = self.extract_jacket(diff)
        wav = os.path.join(TEMP, '{}.wav'.format(self.id))
        out_wav = os.path.join(TEMP, '{}_out.wav'.format(self.id))
        out_mp3 = "{:04d} - {}".format(self.id, self.sanitized)
        if diff is not None:
            diff = self.diff_strings[diff]
            if diff == 'INF':
                diff = self.infname
            out_mp3 += ' [{}]'.format(diff)
        out_mp3 += '.mp3'

        with open(wav, 'wb') as f:
            f.write(dx.data)

        # wavs from 2dx files aren't liked by lame
        sox_args = '-R "{}" -e signed-integer "{}"'.format(wav, out_wav)
        if AMPLIFY:
            sox_args = '--norm ' + sox_args
        run(SOX, sox_args)

        if PROCESS['320']:
            self._lame_enc(jacket, out_wav, os.path.join(OUT320, out_mp3), '-b320')
        if PROCESS['V0']:
            self._lame_enc(jacket, out_wav, os.path.join(OUTV0, out_mp3), '-V0')

        os.remove(jacket)
        os.remove(wav)
        os.remove(out_wav)

    def encode(self):
        for i in range(1, MAX_DIFF+1):
            if self.dx[i]:
                tracks = self.load_2dx(self.dx[i])
                self._convert(tracks[0], i)

        # default map
        if self.dx[0]:
            tracks = self.load_2dx(self.dx[0])

            # doesn't work since IV uses effect tracks again
            #if self.ver > 1 and len(tracks) > 1:

            # literally the only song that does this
            if self.id == 691:
                self._convert(tracks[1], self.diff_map['INF'])
            self._convert(tracks[0])

class Tutorial(Song):
    def __init__(self, folder, xml, all_jackets):
        Song.__init__(self, folder, None, None, xml)

        # finding the latest tutorial jacket, since the dll lies
        dummies = [x for x in all_jackets if x.endswith('dummy_b.ifs')]
        if len(dummies) == 1:
            dummy = dummies[0]
            try:
                self.ver = int(dummy[3:6])
            except ValueError: # II is just jk_dummy
                self.ver = 2
        else:
            self.ver = max(int(x[3:6]) for x in dummies)
            dummy = 'jk_{:03d}_dummy_b.ifs'.format(self.ver)

        self.id = -self.ver
        self.artist = 'Konami'
        self.infVer = 0

        # for infinite infection
        for r in ['[sz:10]', '[sz:12]']:
            self.name = self.name.replace(r, '')

        self.dx = ['__tutorial.2dx']
        self.dx.extend([None]*MAX_DIFF)

        self.jackets = [dummy]
        self.jackets.extend([None]*MAX_DIFF)

    def find_2dx(self):
        pass

    def find_jackets(self):
        pass

def run(exe, arg):
    args = ' '.join((exe, arg))
    FNULL = open(os.devnull, 'w')
    ret = subprocess.call(args, shell=False, stdout=FNULL, stderr=FNULL)

    if ret:
        raise OSError('Called process returned error')

    return ret

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

def fixBrokenChars(name):
    # a bunch of chars get mapped oddly - bemani specific fuckery
    # MISSING: ©
    replacements = [
        ['\u203E', '~'],
        ['\u301C', '～'],
        ['\u49FA', 'ê'],
        ['\u5F5C', 'ū'],
        ['\u66E6', 'à'],
        ['\u66E9', 'è'],
        ['\u8E94', '🐾'],
        ['\u9A2B', 'á'],
        ['\u9A69', 'Ø'],
        ['\u9A6B', 'ā'],
        ['\u9A6A', 'ō'],
        ['\u9AAD', 'ü'],
        ['\u9B2F', 'ī'],
        ['\u9EF7', 'ē'],
        ['\u9F63', 'Ú'],
        ['\u9F67', 'Ä'],
        ['\u973B', '♠'],
        ['\u9F6A', '♣'],
        ['\u9448', '♦'],
        ['\u9F72', '♥'],
        ['\u9F76', '♡'],
        ['\u9F77', 'é'],
    ]
    for rep in replacements:
        name = name.replace(rep[0], rep[1])
    return name

def twoDecimals(num):
    return "{0:.2f}".format(num).rstrip('0').rstrip('.')

def processTutorial(folder, songs, all_jackets):
    dll_path = os.path.join(folder, 'soundvoltex.dll')
    with open(dll_path,'rb') as f:
        dll = f.read()
    pattern = b'<?xml version="1.0" encoding="shift-jis"?><music'
    offset = dll.find(pattern)
    size = 0
    if offset == -1:
        tqdm.write('Warning: {} has no tutorial'.format(os.path.basename(folder)))
        return
    while dll[offset+size] != 0:
        size += 1
    xml = dll[offset:offset+size]
    xml = BeautifulSoup(xml, 'lxml').html.body.music
    tut = Tutorial(folder, xml, all_jackets)
    songs[tut.id] = tut

def processSongs(folder):
    all_2dx = os.listdir(os.path.join(folder, SONG_PATH))
    all_jackets = os.listdir(os.path.join(folder, JACKET_PATH))

    songs = OrderedDict()
    processTutorial(folder, songs, all_jackets)

    path = os.path.join(folder, DB_PATH)
    db = None
    with open(path, 'r', encoding='shift_jisx0213') as f:
        # won't parse as xml, must pretend it's html
        db = BeautifulSoup(f, 'lxml').html.body.mdb

    for entry in tqdm(db.find_all('music'), desc='Loading {}'.format(os.path.basename(folder))):
        song = Song(folder, all_2dx, all_jackets, entry)
        songs[song.id] = song

    return songs

def _load(song):
    song.encode()
    return '{} - {}'.format(song.id, song.name)

if __name__ == '__main__':
    songs = OrderedDict()
    for f in tqdm(FOLDERS, desc='Loading folders'):
        new_songs = processSongs(f)
        songs.update(new_songs)

    filter_func(songs)

    if PROCESS['V0']:
        mkdir_p(OUTV0)
    if PROCESS['320']:
        mkdir_p(OUT320)

    p = Pool()
    for f in tqdm(p.imap_unordered(_load, songs.values()), desc='Encoding', total=len(songs.items())):
        tqdm.write(f)
