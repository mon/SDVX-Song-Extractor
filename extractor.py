# SDVX Song Extractor
# MUST USE PYTHON 3
# `pip install bs4 lxml Pillow`
# Edit FOLDERS, OUT as desired.
# py -3 extractor

# Code values functionality over being good.

from bs4 import BeautifulSoup
import os, subprocess, errno
import shutil
from PIL import Image
import sys

# If you only want some formats, change the unwanted ones to false
PROCESS = {
    'flac' : True,
    '320'  : True,
    'V0'   : True,
}

# the raw files are quite quiet. Normalise them?
AMPLIFY = True

# add as many as you need to get all deleted songs
FOLDERS = ["../Sound Voltex III -Gravity Wars- Final",
           "../Sound Voltex II Infinite Infection"]

OUT = "Sound Voltex III Final Extracted Soundtrack"
ALBUM_NAME = "Sound Voltex Soundtrack"

OUTV0 = os.path.join(OUT, OUT + ' V0')
OUT320 = os.path.join(OUT, OUT + ' 320')

DB_PATH = "data/others/music_db.xml"
JACKET_PATH = "data/graphics/jk"
SONG_PATH = "data/sound"
DX2WAV = "2dx2wavs.exe"
IMGFS_EXTRACT = "dumpImgFS.exe"
TEX2TGA = "tex2tga.exe"
LAME = "lame.exe"
SOX = "sox.exe"

def quote(thing):
    return '"' + thing.replace('"', '\\"') + '"'

DB_PATH = os.path.normpath(DB_PATH)
JACKET_PATH = os.path.normpath(JACKET_PATH)
OUT = os.path.normpath(OUT)
DX2WAV = quote(DX2WAV)
IMGFS_EXTRACT = quote(IMGFS_EXTRACT)
TEX2TGA = quote(TEX2TGA)
LAME = quote(LAME)
SOX = quote(SOX)

def run_nonblocking(exe, arg):
    args = ' '.join((exe, arg))
    FNULL = open(os.devnull, 'w')
    return subprocess.Popen(args, stdout=FNULL, stderr=FNULL, shell=False)

def run(exe, arg, quoteArgs = True):
    if quoteArgs:
        arg = quote(arg)
    args = ' '.join((exe, arg))
    subprocess.call(args, shell=False)

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

def extractJacket(jacket, output):
    path = os.path.join(FOLDER, JACKET_PATH, jacket)
    fsResult = jacket + '_imgfs'
    texBase = fsResult + '_tex'
    texResult = os.path.join(texBase, 'tex000')
    run(IMGFS_EXTRACT, path + '.ifs')
    run(TEX2TGA, os.path.join(fsResult, 'tex', 'texturelist.xml'))
    dest = os.path.join(output, jacket + '.png')
    Image.open(os.path.join(texResult, jacket + '.tga')).save(dest)
    shutil.rmtree(fsResult)
    shutil.rmtree(texBase)
    return dest

def fixBrokenChars(name):
    # a bunch of chars get mapped oddly - bemani specific fuckery
    replacements = [
        ['\u9f76', '♡'],
        ['\u9F72', '♥'],
        ['\u9F6A', '♣'],
        ['\u9F77', 'é'],
        ['\u66E9', 'è'],
        ['\u49FA', 'ê'],
        ['\u66E6', 'à'],
        ['\u9A6B', 'ā'],
        ['\u9EF7', 'ē'],
        ['\u9B2F', 'ī'],
        ['\u9A6A', 'ō'],
        ['\u5F5C', 'ū'],
        ['\u9AAD', 'ü'],
        ['\u9A69', 'Ø'],
        ['\u301C', '～'],
        ['\u203E', '~'],
        ['\u9F67', 'Ä'],
        ['\u9F63', 'Ú']]
    for rep in replacements:
        name = name.replace(rep[0], rep[1])
    return name

def jacketTest(filename):
    return os.path.isfile(os.path.join(FOLDER, JACKET_PATH, filename + ".ifs"))

def dxTest(filename):
    return os.path.isfile(os.path.join(FOLDER, SONG_PATH, filename + ".2dx"))

def getJacket(song, infinite = False):
    jacketName = None
    jacketFormat = "jk_{:03d}_{:04d}_{}_b"
    NOV = 1
    EXH = 3
    INF = 4
    if infinite:
        jacketName = jacketFormat.format(song['ver'], song['id'], INF)
    else:
        jacketName = jacketFormat.format(song['ver'], song['id'], EXH)

    if not jacketTest(jacketName):
        # only 1 specified after all
        jacketName = jacketFormat.format(song['ver'], song['id'], NOV)
    if not jacketTest(jacketName):
        # no novice diff, EG #840
        jacketName = jacketFormat.format(song['ver'], song['id'], INF)

    if not jacketTest(jacketName):
        print(jacketName, "can't be found")
        return None

    return jacketName

def twoDecimals(num):
    return "{0:.2f}".format(num).rstrip('0').rstrip('.')

def lameEnc(song, jacket, wav, mp3, quality):
    bpmStr = ""
    if song['minBpm'] != song['maxBpm']:
        bpmStr = twoDecimals(song['minBpm']) + '-' + twoDecimals(song['maxBpm'])
    else:
        bpmStr = twoDecimals(song['minBpm'])

    return run_nonblocking(LAME, ' '.join([
        quality,
        quote(wav),
        quote(mp3),
        '--tt', quote(song['name']),
        '--ta', quote(song['artist']),
        '--tl', quote(ALBUM_NAME),
        '--tn', quote(str(song['id'])),
        '--tv', 'TPE2="Various Artists"',
        '--tv', 'TPOS=' + str(song['ver']) + '/3',
        '--tv', 'TBPM="' + bpmStr + '"',
        '--ti', quote(jacket),
    ]))

def convert(song, wavPath, infinite = False, jacketName = None):
    sanitized = song['name']
    # strip bad chars
    for c in '\\/:*?"<>|': sanitized = sanitized.replace(c, "")

    # because sox isn't unicode
    outwav = os.path.join(OUT, "temp.wav")
    outmp3 = "{:04d} - {}.mp3".format(song['id'], sanitized)

    if not jacketName:
        jacketName = getJacket(song, infinite)
    outJacket = extractJacket(jacketName, OUT)

    # wavs from 2dx files aren't liked by lame
    if AMPLIFY:
        run(SOX, ' '.join(['-R --norm', quote(wavPath), '-e signed-integer', quote(outwav)]), False)
    else:
        run(SOX, ' '.join([quote(wavPath), '-e signed-integer', quote(outwav)]), False)

    print("Encoding...")
    p1 = lameEnc(song, outJacket, outwav, os.path.join(OUT320, outmp3), '-b320')
    p2 = lameEnc(song, outJacket, outwav, os.path.join(OUTV0, outmp3), '-V0')
    p1.wait()
    p2.wait()
    print("Done!")

    os.remove(outwav)
    os.remove(outJacket)

def extractTutorial():
    song = {
        'name'      : 'Tutorial',
        'id'        : 0,
        'ver'       : 2,
        'infVer'    : 0,
        'label'     : '_',
        'asciiName' : '',
        'artist'    : 'Konami',
        'minBpm'    : 135,
        'maxBpm'    : 135
    }
    dxPath = os.path.join(FOLDER, SONG_PATH, '__tutorial.2dx')
    run(DX2WAV, dxPath)
    convert(song, os.path.join('__tutorial', '01.wav'), False, 'jk_003_dummy_b')
    shutil.rmtree('__tutorial')

def processSongs(startFrom = 0, onlyThese = None):
    mkdir_p(OUTV0)
    mkdir_p(OUT320)
    path = os.path.join(FOLDER, DB_PATH)
    db = None
    with open(path, 'r', encoding='shift_jisx0213') as f:
        # won't parse as xml, must pretend it's html
        db = BeautifulSoup(f, 'lxml').html.body.mdb
    for entry in db.find_all('music'):
        song = {
            'name'      : fixBrokenChars(entry.title_name.text),
            'id'        : int(entry['id']),
            'ver'       : int(entry.version.text),
            'infVer'    : int(entry.inf_ver.text),
            'label'     : entry.label.text,
            'asciiName' : entry.ascii.text,
            'artist'    : fixBrokenChars(entry.artist_name.text),
            'minBpm'    : int(entry.bpm_min.text) / 100.0,
            'maxBpm'    : int(entry.bpm_max.text) / 100.0,
            'volume'    : int(entry.volume.text) / 127.0
        }

        if song['id'] in IDS:
            continue
        IDS.append(song['id'])

        if song['id'] < startFrom:
            continue

        # Use this feature to convert and tag specific song(s)
        if onlyThese != None and song['id'] not in onlyThese:
            continue

        filename = None
        try:
            filename = "{:03d}_{:04d}_{}".format(song['ver'], int(song['label']), song['asciiName'])
        except:
            filename = "{}_{}".format(song['label'], song['asciiName'])
        # because some songs are still annoying
        if not dxTest(filename):
            filename = "{:03d}_{:04d}_{}".format(song['ver'], song['id'], song['asciiName'])
        if not dxTest(filename):
            print(filename, "can't be found")
            break

        dxPath = os.path.join(FOLDER, SONG_PATH, filename + '.2dx')
        run(DX2WAV, dxPath)
        convert(song, os.path.join(filename, '01.wav'))

        # consistency? What consistency?
        if song['id'] == 691:
            song['name'] += " [GRV]"
            convert(song, os.path.join(filename, '02.wav'), True)

        shutil.rmtree(filename)

        # some maps have different songs for INF/GRV
        if dxTest(filename + '_4i'):
            filename += '_4i'
            song['name'] += ['','',' [INF]', ' [GRV]'][song['infVer']]
            infPath = os.path.join(FOLDER, SONG_PATH, filename + '.2dx')
            run(DX2WAV, infPath)
            convert(song, os.path.join(filename, '01.wav'), True)
            shutil.rmtree(filename)

IDS = []
# make it global iunno mang my variable scoping in Python is bad
FOLDER = None
for FOLDER in FOLDERS:
    FOLDER = os.path.normpath(FOLDER)
    processSongs()

extractTutorial()
