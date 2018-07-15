# TiVo To Go Plex Channel Plugin

This Plex plugin uses the TiVo To Go API to watch a stream off of, or download a recorded program from, a TiVo DVR. It requires a Series 2 or newer TiVo with a network connection. The Plex Media Server (PMS) should have a high speed connection between itself and the TiVo.

_Q:_ What would I use this channel for?

_A:_ You can browse to a show on your TiVo through Plex and watch (stream) it without needing to first download it to your PMS.

_Q:_ Can I download something from the TiVo to the Plex Media Server using this channel?

_A:_ Yes! If you enable the download option and specify a folder name, the plugin will display an extra menu item to download the content to your PMS.

   _NOTE:_ You should create a library on your PMS which points to the same directory that you are downloading the files into. If you name the Plex library "TiVo To Go" it will automatically get refreshed when downloads are initiated _and_ when they complete. If
   you want to name the Plex library something different (or include it in multiple libraries) simply add the name(s) in the plugin preferences (see the Steps section below).

- - -
## Installation

### Requirements

- Linux, OSX or Windows Plex Server (no ARM processor NAS support)
- on Linux, OSX or X86 NAS, [curl](https://curl.haxx.se/) must be installed
- 32-bit Java runtime (for [tivolibre](https://github.com/fflewddur/tivolibre))

### Steps

1.  Install [curl](https://curl.haxx.se/) if you don't already have it. 
2.  If you want to use [tivolibre](https://github.com/fflewddur/tivolibre) (see below), make sure a Java runtime for your platform is also installed.
3.  Copy the TiVoToGo.bundle to your plugin directory:
    * Mac: ~/Library/Application Support/Plex Media Server/Plug-ins
    * Windows: C:\Users\\_&lt;username&gt;_\AppData\Local\Plex Media Server\Plug-ins
    * Linux: /var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Plug-ins
4.  Launch the channel via the Plugins or Channels menu in Plex.
5.  Update the plugin settings:
    * Enter your Media Access Key (MAK) from the TiVo
    * If your PMS is on a different subnet than your TiVo(s), enter the TiVo IP address(es), then exit the channel and start it again. Otherwise, leave the IP address field blank and the plug-in should auto-discover your TiVo boxes. You can specify multiple TiVo IP addresses separated by commas if auto-discovery doesn't work for you.
    * If you want to prevent specific TiVo(s) from appearing in the plug-in via auto-discovery, enter the name(s) in the ignore field separated by commas.
    * If you want enable the offline downloads check the "Enable To Go downloads" box and fill in a directory that is writable by the plex user
    * Enter the name of the Plex library to automatically refresh once a download has started. If left blank, this will default to "TiVo To Go." You can enter multiple library names, separated by commas if you want. This lets you add your download directory to multiple libraries using different metadata agents (i.e., for TV Shows and Movies).
    * If you want the plugin to [properly name](https://support.plex.tv/articles/200220687-naming-series-season-based-tv-shows/) your downloaded file (for Plex agent metadata lookups), enter your TiVo Online username and password in the appropriate fields (this is currently broken on Windows, so leave these fields empty (see issue #[5](https://github.com/jradwan/TiVoToGo.bundle/issues/5))).
    * If you want to use [tivolibre](https://github.com/fflewddur/tivolibre) (instead of tivodecode) for better MPEG-TS support, check the "Use tivolibre" box and fill in the path to your platform's Java runtime (ex. /usr/bin/java on Linux). Turn on the "Download TS files" checkbox if you want to download transport stream files (MPEG-TS (.ts) instead of MPEG-PS (.mpg)).

- - -
## To Do

- use the urllib instead of curl
- stop using /tmp/cookies.txt
- use dynamic sockets and a fixed URL for the live stream video
- validate TiVo credentials when saving preferences (in the validatePrefs placeholder)
- set thumbnails for folders, episodes, download action, etc.
- fix Suggestions folder (issue #[1](https://github.com/jradwan/TiVoToGo.bundle/issues/1))
- get RPC call for episode naming working on Windows (issue #[5](https://github.com/jradwan/TiVoToGo.bundle/issues/5))

- - -
## Contact

Jeremy C. Radwan

- https://github.com/jradwan
- http://www.windracer.net/blog

- - -
## References

rpcSearch125.py from [MetaGenerator 3](https://pytivo.sourceforge.io/forum/metagenerator-version-3-t1786.html)

https://github.com/tivoguy/TiVoToGo.bundle

https://github.com/sander1/TiVoToGo.bundle
