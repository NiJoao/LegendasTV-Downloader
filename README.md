LegendasTV-Downloader
=======================

Single-file script that scans a folder for videos and downloads subtitles for all of them from legendas.tv

NO user input needed, totally automatic.

Works great for TV-Shows, but gets unsynced subtitles for some movies, depending on naming schemes on both the file and legendas.tv website.

Please, use the **issues** tab to make suggestions and file bugs.

## Quick HowTo:

1. Install python (v2.7 recommended) and the modules: BeautifulSoup4, rarfile
2. Open the file 'ltv-downloader.py' with any text editor
3. Edit the first configuration lines with your username and password for legendas.tv website
4. Drag-and-Drop videos or folders on 'ltv-downloader.py'
5. Enjoy!


## More details:

### What it does:

The script totally automates the downloading and renaming of subtitles from legendas.tv.
NO user input is required.

It accepts movies/shows files as arguments (Drag-and-dropped too).
Then it analyzes the file names, searches and chooses the best subtitle from legendasTV, downloads it and renames.
It also accepts folders as input, analyzing all the files inside, and optionally recursing through all subfolders.

Many configurations are available for the user to choose, as explained in the *Configuration* section below.
The default settings are suited to my case and library.
I recommend you to look at the default settings below.

**Carefull** with default settings, it stores the downloaded subtitles with the language code appended (e.g. \*.br.srt),
and **will delete already existing subtitles** that don't have the language code!
(Actually, it replaces them with a hardlink to the best language available.)

____

### Installation

* Download https://raw.github.com/NiJoao/LegendasTV-Downloader/master/ltv-downloader.py
* Copy it to your Series folder, or any other place you wish acessible to drag-and-drop your movies collection
* You can create shortcuts to the script in any folders you wish
* Edit the file to configure it. Read next session for more info
* Install python and the packages with the following methods

##### Linux Installation

    sudo apt-get install unrar-free python2.7 python-pip python-dev build-essential
    pip install beautifulsoup4 rarfile

##### Windows Installation

* Download and install "Python 2.7.x Windows Installer" from http://www.python.org/download/
* Add to the PATH Environment Variable: ** ;C:\Python27;C:\Python27\Scripts **
* Download and run http://python-distribute.org/distribute_setup.py
* Download and run https://raw.github.com/pypa/pip/master/contrib/get-pip.py
* Open a command line (Win+R, cmd) and type:
  * pip install beautifulsoup4 rarfile

____

### Configuration

The user should open "ltv-downloader.py" using a text editor to configure the script.

Here is the description of all the configuration options, available at the beggining of the script

##### username & password

If you need explanation on these, press alt-f4
* default: empty

##### default_folder

Default folder analyzed when no argument is given (user double-clicked ltv-downloader.py)
A '.' means the current working dir, the local folder where the script or shortcut was run from
* default: '.'

##### preferred_languages

Ordered list of desired languages.
The script will try to download preferentially from this order, downloading the best available language

If the append_language option is True, if a subtitle with the first language already exists on disk, it is skipped.
If other languages exist, the script will try to upgrade it, resulting in mutiple subtitles on disk.
* default: ['pt', 'br', 'en']

##### rename_subtitle 

If the subtitle file should be renamed to match the video's filename
* default: True

##### append_language 

If used together with rename_subtitle, the subtitle will have the language-code appended (e.g. ShowName.pt.srt)
* default: True

##### hardlink_without_lang_to_best_sub

This option is useful for some players that can't read subtitle files with language-codes in the name. (e.g. Samsung televisions)
If used together with append_language, a hardlink without language-code is created with the shows name (e.g. ShowName.srt), always pointing to the best downloaded subtitle language.
In a file explorer, if behaves like any other file, looking like a simple copy of the coded-subtitle, but it occupies no disk-space and is instantaneous to create.
* default: True

##### confidence_threshold 

Advanced stuff. Don't mess with it, unless you are really confortable in your chair.
* default: 50

##### recursive_folders 

If subfolders should be analyzed recursively.
In my case I want it off. You can always activate it from the command line with the -r argument.
If the '-r' argument is used, any folders FOLLoWING it will be recursed. Previous folders are not recursed.
(e.g. ltv-downloader.py .\NotRecursed\ -r .\Recursed\ )
* default: False

##### clean_original_filename & clean_name_from  

With these options, the specified tags and any surrouding brackets/parentesis will be removed from the analyzed files.
(e.g. ShowName.[VTV].avi is renamed to ShowName.avi
* default: True, ['VTV', 'www.torentz.3xforum.ro']

##### valid_subtitle_extensions & valid_video_extensions

Valid file extensions to be parsed

##### valid_extension_modifiers

Valid extra file extensions, usually used when the file is still downloading.
These extensions are trimmed from the names, but the remaining/2nd extension is validated against the other valid_extensions options

##### known_release_groups

The release group is sometimes hard to find from the filename, mainly on Movies where there is no standard naming scheme.
Having the release group can drastically improve the subtitles search results.
This option specifies a list of some common groups, that are matched against the filename.
If this fails to find the group, we use other methods to search for it.
