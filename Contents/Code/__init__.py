from subprocess import Popen, PIPE
from signal import *
from os import kill, getpid, environ, path, unlink, open, close, write, O_RDWR, O_CREAT
import sys
import platform, tempfile
from time import sleep
import urllib2, cookielib, ssl
from lxml import etree
import base64
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import thread
import string
import re
import copy
import socket
from collections import deque
import zeroconf

NAME = "TiVo To Go"
BUNDLE_NAME = "TiVoToGo.bundle"

TIVO_CONTENT_FOLDER     = "x-tivo-container/folder"
TIVO_CONTENT_SHOW_TTS   = "video/x-tivo-raw-tts"
TIVO_CONTENT_SHOW_PES   = "video/x-tivo-raw-pes"

TIVO_PORT            = 49492

TIVO_XML_NAMESPACE   = 'http://www.tivo.com/developer/calypso-protocol-1.6/'
TIVO_LIST_PATH       = "/TiVoConnect?Command=QueryContainer&Recurse=No&Container=%2FNowPlaying"

DownloadThread = None
GL_CURL_PID = 0
DL_QUEUE = deque()

# For the UpdateTTGFolder function
HOST = 'http://localhost:32400'
SECTIONS = '/library/sections/'
PLEXTOKEN = environ['PLEXTOKEN'] if 'PLEXTOKEN' in environ else ''

# use portions of rpcSearch125.py (thanks to dlfl/MG3) for TiVo Mind server calls (to look up episode information)
import logging
import random
import json

TIVO_ADDR     = 'middlemind.tivo.com'
TIVO_PORT_SSL = 443
session_id    = random.randrange(0x26c000, 0x27dc20)
rpc_id        = 0
body_id       = ''


####################################################################################################
def Start():
    ObjectContainer.title1 = NAME
    HTTP.CacheTime = 3600*5

####################################################################################################
def getMyMAK():
    return Prefs['MAK'] or ""


####################################################################################################
def getNameFromXML(show, name, default=""):
    result = show.xpath(name, namespaces={'g': TIVO_XML_NAMESPACE})
    if (len(result) > 0):
        return result[0]
    else:
        return default

####################################################################################################

def getTivoShowsByIPURL(tivoip, url, dir):
    anchoroffset = 0
    offset = 16
    endanchor = 0

    # Loop for all pages of the TiVo Now Playing
    while True:
        qurl = url + "&AnchorOffset=%i" % anchoroffset
        Log("getTivoShowsByIPURL: %s" % qurl)
        try:
            authhandler = urllib2.HTTPDigestAuthHandler()
            authhandler.add_password("TiVo DVR", "https://" + tivoip + ":443/", "tivo", getMyMAK())
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
            opener = urllib2.build_opener(urllib2.HTTPSHandler(context=ssl_context), authhandler)
            pagehandle = opener.open(qurl)
        except IOError, e:
            Log("Got a URLError trying to open %s" % url)
            if hasattr(e, 'code'):
                Log("Failed with code : %s" % e.code)
                if (int(e.code) == 401):
                    dir.SetMessage("Couldn't authenticate", "Failed to authenticate to TiVo.  Is the Media Access Key correct?")
                else:
                    dir.SetMessage("Couldn't connect", "Failed to connect to TiVo")
            if hasattr(e, 'reason'):
                Log("Failed with reason : %s" % e.reason)
            return dir
        except:
            Log("Unexpected error trying to open %s" % url)
            return dir

        myetree = etree.parse(pagehandle).getroot()
        page_total_items = getNameFromXML(myetree, "g:Details/g:TotalItems/text()")
        if page_total_items != "":
            endanchor = int(page_total_items)
        if anchoroffset == 0:
            page_item_count = getNameFromXML(myetree, "g:ItemCount/text()")
            if page_item_count != "":
                offset = int(page_item_count)

        for show in myetree.xpath("g:Item", namespaces={'g': TIVO_XML_NAMESPACE}):
            show_name = getNameFromXML(show, "g:Details/g:Title/text()")
            show_content_type = getNameFromXML(show, "g:Details/g:ContentType/text()")
            if (show_content_type == TIVO_CONTENT_FOLDER):
                show_total_items = int(getNameFromXML(show, "g:Details/g:TotalItems/text()"))
                show_folder_url = getNameFromXML(show, "g:Links/g:Content/g:Url/text()")
                show_folder_id = show_folder_url[show_folder_url.rfind("%2F")+3:]
                dir.add(DirectoryObject(key=Callback(getTivoShows, tivoip=tivoip, url=show_folder_url, showName=show_name), title=L("%s (%s)" % (show_name, show_total_items))))

            elif ((show_content_type == TIVO_CONTENT_SHOW_TTS) or
                        (show_content_type == TIVO_CONTENT_SHOW_PES)) :
                show_duration = getNameFromXML(show, "g:Details/g:Duration/text()")
                show_episode_name = getNameFromXML(show,"g:Details/g:EpisodeTitle/text()")
                show_episode_num = getNameFromXML(show, "g:Details/g:EpisodeNumber/text()")
                show_desc = getNameFromXML(show, "g:Details/g:Description/text()")
                show_url = getNameFromXML(show, "g:Links/g:Content/g:Url/text()")
                show_in_progress = getNameFromXML(show,"g:Details/g:InProgress/text()")
                show_copyright = getNameFromXML(show, "g:Details/g:CopyProtected/text()")

                show_programid = getNameFromXML(show, "g:Details/g:ProgramId/text()")
                if (show_programid[:2] == "MV"):
                    show_type_thumb = 'art-movie.jpg'
                else:
                    show_type_thumb = 'art-tv.jpg'

                show_desc = show_desc[:show_desc.rfind("Copyright Rovi, Inc")]
                show_id  =  show_url[show_url.rfind("&id=")+4:]
                if (show_episode_num != ""):
                    show_season_num = show_episode_num[:-2]
                    show_season_ep_num = show_episode_num[-2:]

                if show_episode_name != "":
                    target_name = show_name + ' - ' + show_episode_name
                else:
                    target_name = show_name

                if show_copyright != "Yes" and show_in_progress != "Yes":
                    localurl = "http://127.0.0.1:" + str(TIVO_PORT) + "/" + base64.b64encode(show_url, "-_")
                    if Prefs['togo']:
                        dir.add(DirectoryObject(key=Callback(getShowContainer, url = localurl,
                                                             show_url = show_url,
                                                             title = target_name,
                                                             summary = show_desc,
                                                             thumb = show_type_thumb,
                                                             tagline = show_episode_name,
                                                             duration = show_duration),
                                                title=L(target_name)))
                    else:
                        dir.add(CreateVideoClipObject(url = localurl,
                                                      title = target_name,
                                                      summary = show_desc,
                                                      thumb = show_type_thumb,
                                                      tagline = show_episode_name,
                                                      duration = show_duration))
                else:
                    Log("Found a different content type: " + show_content_type)
        if endanchor == 0 or anchoroffset + offset >= endanchor:
            break
        else:
            anchoroffset += offset

    return dir

####################################################################################################

@route('/video/tivotogo/createvideoclipobject', container=bool, duration=int)
def CreateVideoClipObject(url, title, thumb, container = False, summary="", duration=14400000, tagline="", **kwargs):
    Log.Debug("Starting a thread")
    thread.start_new_thread(TivoServerThread, ("127.0.0.1", TIVO_PORT))
    Log.Debug("Done starting a thread")
    vco = VideoClipObject(
        key = Callback(CreateVideoClipObject, url = url, title = title, thumb = thumb,
                       tagline = tagline,
                       summary = summary,
                       container = True,
                       duration = duration),
        rating_key = url,
        title = title,
        thumb = thumb,
        summary = summary,
        tagline = tagline,
        duration = int(duration),
        items = [
            MediaObject(
                parts = [
                    PartObject(
                        key = url
                    )
                ],
                optimized_for_streaming = True
            )
        ]
    )

    if container:
        return ObjectContainer(objects = [vco])

    return vco

####################################################################################################
def getTvd():
    # Lack of a PMS api for a local path means we find the local
    # plugin resources the hard way duplicating some of Plugin.py
    if sys.platform == "darwin":
        return path.join(environ['HOME'],
                         'Library',
                         'Application Support',
                         'Plex Media Server',
                         'Plug-ins',
                         BUNDLE_NAME,
                         'Contents',
                         'Resources',
                         'tivodecode.osx')

    if 'PLEXLOCALAPPDATA' in environ:
        key = 'PLEXLOCALAPPDATA'
    else:
        key = 'LOCALAPPDATA'

    if sys.platform == "win32":
        return path.join(environ[key],
                         'Plex Media Server',
                         'Plug-ins',
                         BUNDLE_NAME,
                         'Contents',
                         'Resources',
                         'win',
                         'tivodecode.exe')
    # Linux 64
    if platform.architecture()[0] == "64bit":
        return path.join(environ[key],
                         'Plex Media Server',
                         'Plug-ins',
                         BUNDLE_NAME,
                         'Contents',
                         'Resources',
                         'tivodecode.x86_64')
    # Linux 32
    return path.join(environ[key],
                     'Plex Media Server',
                     'Plug-ins',
                     BUNDLE_NAME,
                     'Contents',
                     'Resources',
                     'tivodecode')

####################################################################################################
def getTvl():

    # similar to getTvd above, except build the path to the TiVoLibre java file instead

    # OSX
    if sys.platform == "darwin":
        return path.join(environ['HOME'],
                         'Library',
                         'Application Support',
                         'Plex Media Server',
                         'Plug-ins',
                         BUNDLE_NAME,
                         'Contents',
                         'Resources',
                         'TivoDecoder.jar')

    if 'PLEXLOCALAPPDATA' in environ:
        key = 'PLEXLOCALAPPDATA'
    else:
        key = 'LOCALAPPDATA'

    # Windows and Linux
    return path.join(environ[key],
                     'Plex Media Server',
                     'Plug-ins',
                     BUNDLE_NAME,
                     'Contents',
                     'Resources',
                     'TivoDecoder.jar')

####################################################################################################
def getCurl():
    if sys.platform != "win32":
        return "/usr/bin/curl"

    if 'PLEXLOCALAPPDATA' in environ:
        key = 'PLEXLOCALAPPDATA'
    else:
        key = 'LOCALAPPDATA'

    if sys.platform == "win32":
        return path.join(environ[key],
                         'Plex Media Server',
                         'Plug-ins',
                         BUNDLE_NAME,
                         'Contents',
                         'Resources',
                         'win',
                         'curl.exe')

####################################################################################################

class MyVideoHandler(BaseHTTPRequestHandler):

  def do_HEAD(self):
    try:
      self.send_response(200)
      self.send_header('Content-Type', 'video/mpeg2')
      self.end_headers()
      return
    except Exception, e:
      Log("do_HEAD error: %s" % e)

  def do_GET(self):
    try:
      url = base64.b64decode(string.split(self.path[1:], "/")[0], "-_")
      Log("GET URL: %s" % url)
      if sys.platform != "win32":
          self.send_response(200)
      self.send_header('Content-type', 'video/mpeg2')
      self.end_headers()
      if "LD_LIBRARY_PATH" in environ.keys():
        del environ["LD_LIBRARY_PATH"]
      curl = getCurl()
      Log.Debug("CMD: \"%s\" \"%s\" %s %s %s %s %s \"%s\"" % (curl, url, "--digest", "-s", "-u", "tivo:"+getMyMAK(), "-c", path.join(tempfile.gettempdir(),"cookies.txt")))
      curlp = Popen([curl, url, "--digest", "-s", "-u", "tivo:"+getMyMAK(), "-c", path.join(tempfile.gettempdir(),"cookies.txt")], stdout=PIPE)
      if Prefs['tivolibre']:
          tvd = getTvl()
          java_path = Prefs['java_path']
          Log.Debug("PIPED to: \"%s\" %s \"%s\" %s %s %s" % (java_path, "-jar", tvd, "-m", getMyMAK(), "-"))
          if sys.platform == "win32":
              tivodecode = Popen([java_path, "-jar", tvd, "-m", getMyMAK(), "-"],stdin=curlp.stdout, shell=True, stdout=PIPE)
          else:
              tivodecode = Popen([java_path, "-jar", tvd, "-m", getMyMAK(), "-"],stdin=curlp.stdout, stdout=PIPE)
      else:
          tvd = getTvd()
          Log.Debug("PIPED to: \"%s\" %s %s %s" % (tvd, "-m", getMyMAK(), "-"))
          tivodecode = Popen([tvd, "-m", getMyMAK(), "-"],stdin=curlp.stdout, stdout=PIPE)
      Log("Starting decoder")
      while True:
          data = tivodecode.stdout.read(4192)
          if not data:
              break
          self.wfile.write(data)

    except Exception, e:
      Log("Unexpected error: %s" % e)

    try:
      kill(curlp.pid, SIGTERM)
      kill(tivodecode.pid, SIGTERM)
    except:
      Log("Self-exit of tivodecode/curl")

    Log("tivodecode/curl terminated")
    return

  def do_POST(self):
    Log("Got a POST")

####################################################################################################

def TivoServerThread(ip, port):
  try:
    httpserver = HTTPServer((ip, port), MyVideoHandler)
    Log("Server starting: port %i, PID %i" % (port, getpid()))
    httpserver.allow_reuse_address = True
    httpserver.serve_forever()
    Log("Server ooopsed out: port %i" % port)
  except :
    Log("Server already running or port in use")
  
####################################################################################################

def TivoVideo(count, pathNouns):
  Log("Starting a thread")
  thread.start_new_thread(TivoServerThread, ("127.0.0.1", TIVO_PORT))
  Log("Done starting a thread")
  url = "http://127.0.0.1:" + str(TIVO_PORT) + "/" + pathNouns[1] + "/" + pathNouns[2]
  Log("TivoVideo: URL %s" % url)
  return Plugin.Redirect (url)


####################################################################################################

@route("/video/tivotogo/showcontainer")
def getShowContainer(url, show_url, title, summary, thumb, tagline, duration):
    oc = ObjectContainer(title2=L(title))
    oc.add(CreateVideoClipObject(url = url,
                                 title = title,
                                 summary = summary,
                                 thumb = R(thumb),
                                 tagline = tagline,
                                 duration = duration))
    oc.add(DirectoryObject(key = Callback(downloadLocal, url=show_url, title=title, tagline=tagline), title = 'Download Locally'))
    return oc

####################################################################################################
def UpdateTTGFolder():
    try:
        sections = XML.ElementFromURL(HOST + SECTIONS + '?X-Plex-Token=' + PLEXTOKEN, cacheTime=0).xpath('//Directory')
        togoupdatedir = Prefs['togoupdatedir'].split(",") or "TiVo To Go"
        for section in sections:
            key = section.get('key')
            title = section.get('title')
            for current_dir in togoupdatedir:
                if title == current_dir:
                    Log.Info('Updating library #%s - %s' % (key, title))
                    HTTP.Request(HOST + SECTIONS + key + '/refresh?X-Plex-Token=' + PLEXTOKEN, cacheTime=0).content
    except Exception, e:
        Log("Error updating TTG folder: %s" % e)

####################################################################################################

def dlThread():
    global GL_CURL_PID
    global DownloadThread
    global DL_QUEUE

    while True:
        if DL_QUEUE:
            (fileName, url) = DL_QUEUE[0]
        else:
            break
        try:
            Log("Downloading: %s from: %s", fileName, url)
            curl = getCurl()
            Log.Debug("CMD: \"%s\" \"%s\" %s %s %s %s %s \"%s\"" % (curl, url, "--digest", "-s", "-u", "tivo:"+getMyMAK(), "-c", path.join(tempfile.gettempdir(),"cookies.txt")))
            if "LD_LIBRARY_PATH" in environ.keys():
                del environ["LD_LIBRARY_PATH"]
            try:
                unlink(path.join(tempfile.gettempdir(),"cookies.txt"))
            except:
                pass
            curlp = Popen([curl, url, "--digest", "-s", "-u", "tivo:"+getMyMAK(), "-c", path.join(tempfile.gettempdir(),"cookies.txt")], stdout=PIPE)
            if Prefs['tivolibre']: 
                tvd = getTvl()
                java_path = Prefs['java_path']
                Log.Debug("PIPED to: \"%s\" %s \"%s\" %s %s %s \"%s\" %s" % (java_path, "-jar", tvd, "-m", getMyMAK(), "-o", fileName, "-"))
                if sys.platform == "win32":
                    tivodecode = Popen([java_path, "-jar", tvd, "-m", getMyMAK(), "-o", fileName, "-"], stdin=curlp.stdout, shell=True)
                else:
                    tivodecode = Popen([java_path, "-jar", tvd, "-m", getMyMAK(), "-o", fileName, "-"], stdin=curlp.stdout)
            else:
                tvd = getTvd()
                Log.Debug("PIPED to: \"%s\" %s %s %s \"%s\" %s" % (tvd, "-m", getMyMAK(), "-o", fileName, "-"))
                tivodecode = Popen([tvd, "-m", getMyMAK(), "-o", fileName, "-"], stdin=curlp.stdout)
            GL_CURL_PID = curlp.pid
            # Wait two seconds for it to get going and then issue a update for the TiVo folder
            sleep(2)
            UpdateTTGFolder()
            tivodecode.wait()
            kill(curlp.pid, SIGTERM)
            sleep(1)
        except Exception, e:
            Log("Error in download thread: %s" % e)
        # Issue a refresh to the TTG folder
        UpdateTTGFolder()
        DL_QUEUE.popleft()
        Log("Download complete: %s" % fileName)
        GL_CURL_PID = 0
    DownloadThread = None

####################################################################################################

@route("/video/tivotogo/downloadlocal")
def downloadLocal(url, title, tagline):
    global DownloadThread
    global DL_QUEUE
    ttgdir = Prefs['togodir']
    if not ttgdir:
        return ObjectContainer(header='Error', message='TiVo To Go download directory is not set in preferences.', title2='ERROR: No TTG directory')
    try:
        pth = path.join(ttgdir, "tmp.txt")
        f = open(pth, O_CREAT | O_RDWR)
        write(f, "Test123")
        close(f)
        unlink(pth)
    except Exception, e:
        Log("TTG exception: %s" % e)
        return ObjectContainer(header='Error', message='TiVo To Go download directory is not writeable', title2='ERROR: Cannot Write to TTG directory')

    Log("URL: %s" % url)
    Log("Title: %s" % title)

    # use a TiVo Mind RPC call to retrieve the season/episode number of the recording, if applicable
    rpc_username = Prefs['rpc_username']
    rpc_password = Prefs['rpc_password']
    if tagline and rpc_username and rpc_password:
        title_search = title[:title.find(" - ")]
        Log("Search title  : %s" % title_search)
        Log("Search episode: %s" % tagline)
        Log("Executing episodeSearch")
        remote = Remote(rpc_username, rpc_password)
        result = remote.episodeSearch(title_search, tagline)
        content = result.get('content')
        if content:
            for c in content:
                seasonNum  = str(c.get('seasonNumber')).zfill(2)
                episodeNum = str(c.get('episodeNum')).lstrip('[').rstrip(']').zfill(2)
                if seasonNum != "None" and episodeNum != "None":
                    title = title_search + ' S' + seasonNum + 'E' + episodeNum + ' ' + tagline
        Log("Updated title : %s" % title)

    try:
        valid_chars = list("-_.() %s%s" % (string.ascii_letters, string.digits))
        title = ''.join(c for c in list(title) if c in valid_chars)
        if Prefs['tivolibre'] and Prefs['ts-downloads']:
            url = url + "&Format=video/x-tivo-mpeg-ts"
            fileName = path.join(ttgdir, title + ".ts")
        else:
            url = url + "&Format=video/x-tivo-mpeg"
            fileName = path.join(ttgdir, title + ".mpg")
        jobs = copy.deepcopy(DL_QUEUE)
        do_dl = True
        while jobs:
            (tryName, tryURL) = jobs.popleft()
            if (tryName == fileName):
                do_dl = False
        if do_dl:
            DL_QUEUE.append((fileName, url))
            # Race found on OSX setting the thread where it can
            # exit so fast the global has a data hazard
            if not DownloadThread or len(DL_QUEUE) == 1:
                DownloadThread = Thread.Create(dlThread)
            message = 'Queued download of: %s' % title
            title2 = 'Download Queued'
        else:
            message = 'Already queued: %s' % title
            title2 = 'Download Queued'
    except Exception, e:
        DownloadThread = None
        Log("Error starting download thread: %s" % e)
        message = 'Error starting the download thread'
        title2 = 'Download Error'

    return ObjectContainer(header=title2, message=message, title2=title2)

####################################################################################################

def discoverTiVo(oc):

    class ZCListener:
        def __init__(self, names):
            self.names = names

        def removeService(self, server, type, name):
            self.names.remove(name)

        def addService(self, server, type, name):
            self.names.append(name)

    REMOTE = '_tivo-videos._tcp.local.'
    tivo_names = []

    # Get the names of TiVos offering network remote control
    try:
        serv = zeroconf.Zeroconf()
        browser = zeroconf.ServiceBrowser(serv, REMOTE, ZCListener(tivo_names))
    except Exception, e:
        Log("Error staring zeroconf: %s" % e)
        return oc

    # Give them a second to respond
    sleep(0.7)

    # For proxied TiVos, remove the original and any black listed tivos
    browseblacklist = map(str.lstrip, ((Prefs['browseblacklist'] or "").split(",")))
    for t in tivo_names[:]:
        if t.split(".")[0] in browseblacklist:
            tivo_names.remove(t)
            continue
        if t.startswith('Proxy('):
            try:
                t = t.replace('.' + REMOTE, '')[6:-1] + '.' + REMOTE
                tivo_names.remove(t)
            except:
                pass
    Log("%s TiVo(s) auto-discovered." % len(tivo_names))

    # Now get the addresses -- this is the slow part
    swversion = re.compile('(\d*.\d*)').findall
    for t in tivo_names:
        Log("Found TiVo by name: %s" % t)
        s = serv.getServiceInfo(REMOTE, t)
        if s:
            tivoName = t.replace('.' + REMOTE, '')
            addr = socket.inet_ntoa(s.getAddress())
            try:
                port = s.getPort()
                url_proto = s.getProperties()['protocol']
                url_path = s.getProperties()['path']
                url = "%s://%s:%s%s" % (url_proto, addr, port, url_path)
                Log("Found TiVo URL %s" % url)
                if len(tivo_names) == 1:
                    # if only one TiVo was found, just list the contents
                    getTivoShowsByIPURL(addr, url, oc)
                else:
                    oc.add(DirectoryObject(key=Callback(getTivoShows, tivoName=tivoName, url=url, tivoip=addr), title=L(tivoName)))
            except Exception, e:
                Log("Error finding TiVo: %s" % e)
                pass

    serv.close()
    return oc

####################################################################################################

@route("/video/tivotogo/shows")
def getTivoShows(tivoName="", url="", tivoip="", showName=""):
    if showName == "":
        oc = ObjectContainer(title2=L(tivoName))
    else:
        oc = ObjectContainer(title2=L(showName))

    if url == "":
        url = "https://" + tivoip + ":443" + TIVO_LIST_PATH
    return getTivoShowsByIPURL(tivoip, url, oc)

####################################################################################################

@route('/video/tivotogo/getStatus')
def getStatus(rand, execkill=0):
    global DownloadThread
    global GL_CURL_PID
    global DL_QUEUE
    oc = ObjectContainer(title2='Downloading')
    if execkill and GL_CURL_PID:
        kill(GL_CURL_PID, SIGTERM)
        sleep(2)
    jobs = copy.deepcopy(DL_QUEUE)
    if DownloadThread and jobs:
        if jobs:
            (fileName, url) = jobs.popleft()
            oc.add(DirectoryObject(key = Callback(getStatus, rand=str(Util.Random())), title = 'Running: %s' % fileName))
        while jobs:
            (fileName, url) = jobs.popleft()
            oc.add(DirectoryObject(key = Callback(getStatus, rand=str(Util.Random())), title = 'Queued: %s' % fileName))
        oc.add(DirectoryObject(key = Callback(getStatus, rand=str(Util.Random()), execkill = 1), title = 'Kill current job ...'))
    else:
        oc.add(DirectoryObject(key = Callback(getStatus, rand=str(Util.Random())), title = 'Job Queue Empty'))
    oc.add(DirectoryObject(key = Callback(getStatus, rand=str(Util.Random())), title = 'Refresh'))
    return oc

####################################################################################################

@handler("/video/tivotogo", NAME, thumb="icon-default.jpg", art="art-default.jpg")
def MainMenu():

    myMAK = getMyMAK()

    oc = ObjectContainer()

    if (len(myMAK) == 10):
        tivoName = Prefs['tivoStaticIP'] or ""
        if tivoName == "":
            discoverTiVo(oc)
        else:
            tivoList = tivoName.replace(' ','').split(',')
            Log("%s TiVo(s) specified." % len(tivoList))
            if len(tivoList) == 1:
                # if only one TiVo is specified, just list the contents
                url = "https://" + tivoList[0] + ":443" + TIVO_LIST_PATH
                getTivoShowsByIPURL(tivoList[0], url, oc)
            else:
                for x in range (0, len(tivoList)) :
                    oc.add(DirectoryObject(key=Callback(getTivoShows, tivoName=tivoList[x], tivoip=tivoList[x]), title=L(tivoList[x])))
    global DownloadThread
    if DownloadThread:
        oc.add(DirectoryObject(key = Callback(getStatus, rand=str(Util.Random())), title = 'Active Downloads'))
    oc.add(PrefsObject(title=L("Preferences ...")))

    return oc

####################################################################################################

# use portions of rpcSearch125.py (thanks to dlfl/MG3) for TiVo Mind server calls (to look up episode information)

def RpcRequest(type, monitor=False, **kwargs):
  global rpc_id
  rpc_id += 1

  headers = '\r\n'.join((
      'Type: request',
      'RpcId: %d' % rpc_id,
      'SchemaVersion: 14',
      'Content-Type: application/json',
      'RequestType: %s' % type,
      'ResponseCount: %s' % (monitor and 'multiple' or 'single'),
      'BodyId: %s' % body_id,
      'X-ApplicationName: Quicksilver',
      'X-ApplicationVersion: 1.2',
      'X-ApplicationSessionId: 0x%x' % session_id,
      )) + '\r\n'

  req_obj = dict(**kwargs)
  req_obj.update({'type': type})

  body = json.dumps(req_obj) + '\n'

  # The "+ 2" is for the '\r\n' we'll add to the headers next.
  start_line = 'MRPC/2 %d %d' % (len(headers) + 2, len(body))

  return '\r\n'.join((start_line, headers, body))

class Remote(object):
  username = ''
  password = ''


  def __init__(self, myusername, mypassword):
    username = myusername
    password = mypassword
    self.buf = ''
    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    certfile_path = path.join(sys.path[0],"cdata.pem")
    self.ssl_socket = ssl.wrap_socket(self.socket, certfile=certfile_path)
    try:
      self.ssl_socket.connect((TIVO_ADDR, TIVO_PORT_SSL))
    except:
      Log("Connect error")
    try:
      self.Auth(username, password)
    except:
      Log("Credential error")

  def Read(self):
    start_line = ''
    head_len = None
    body_len = None

    while True:
      self.buf = self.buf + self.ssl_socket.read(16)
      match = re.match(r'MRPC/2 (\d+) (\d+)\r\n', self.buf)
      if match:
        start_line = match.group(0)
        head_len = int(match.group(1))
        body_len = int(match.group(2))
        break

    need_len = len(start_line) + head_len + body_len
    while len(self.buf) < need_len:
      self.buf = self.buf + self.ssl_socket.read(1024)
    buf = self.buf[:need_len]
    self.buf = self.buf[need_len:]

    logging.debug('READ %s', buf)
    return json.loads(buf[-1 * body_len:])

  def Write(self, data):
    logging.debug('SEND %s', data)
    self.ssl_socket.send(data)

  def Auth(self, username, password):
    self.Write(RpcRequest('bodyAuthenticate',
        credential={
            'type': 'mmaCredential',
            'username': username,
            'password': password,
            }
        ))
    result = self.Read()
    if result['status'] != 'success':
      Log("Authentication failed!  Got: %s" % result)
      sys.exit(1)

  def episodeSearch(self, title, subtitle):
    req = RpcRequest('contentSearch',
      title = title,
      subtitle = subtitle,
      # only return the first match; this will cause issues with multi-part episodes
      # but it's just a hack anyway
      count = 1
    )
    self.Write(req)
    result = self.Read()
    return result

###################################################################################################

def ValidatePrefs():
    pass

