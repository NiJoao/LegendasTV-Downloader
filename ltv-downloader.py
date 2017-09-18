#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals    # at top of module

#### User Configurations ####

## Fill yours - This is REQUIRED by the LTV website.
ltv_username = 'USERNAME'
ltv_password = 'PASS'

# Folder to scan when no arguments are passed
default_folder = '.'

# Ordered, from: pt, br, en
preferred_languages = ['pt','br','en']
# Rename downloaded subtitles to the same name of the video file, and append language code
rename_subtitle = True
append_language = True
# Download one subtitle file for each of the prefered languages
download_each_lang = False
# Remove old subtitle languages when a prefered becomes available
clean_old_language = False

# Append a confidence/quality number to then end of the subtitle file. Allows "upgrading" with the same language
# Most players ignore this last number and correctly identify the srt file. If not, make this False
append_confidence = False

# Stop if #-Lang is already present: 1-PT, 2-PT/BR, 3-EN/PT/BR etc
stopSearchWhenExistsLang = 1

# Keeps a subtitle with the same name of the video (hard)linking to the best available subtitle.
# Occupies no space, but only useful for some old playeres that don't support language codes in subtitle files
hardlink_without_lang_to_best_sub = False

# Set this to 80 or 90 if you just want to download the best languague and subtitle
confidence_threshold = 50 

# Recursivity also becomes active after a '-r' argument
recursive_folders = False

# Append or update IMDB rating at the end of movie folders
# Folders must have the movie name followed by the year inside parenthesis, otherwise they are ignored
# eg: "Milk (2008)" becomes: "Milk (2008) [7.7]"
append_iMDBRating = True

# Rename and clean videos and accompanying files from this garbage-tags 
fix_ETTV_subfolder = True

# Rename and clean videos and accompanying files from this garbage-tags 
clean_original_filename = True
clean_name_from = ['VTV','www.torentz.3xforum.ro','MyTV','RARBG','rartv','eztv','ettv']


Debug = 0

####### End of regular user configurations #######

## Set this flag using -f as parameter, to force search and replace all subtitles. 
## This option is implied when only one argument is passed (single file dragged & dropped)
ForceSearch=False
OnlyIMDBRating = False

## LegendasTV timeout and number of threads to use. Increasing them too high may affect the website performance, please be careful
ltv_timeout = 15
thread_count = 5

#### Known Arrays

# No need to change those, but feel free to add/remove some
valid_subtitle_extensions = ['srt','txt','aas','ssa','sub','smi']
valid_video_extensions = ['avi','mkv','mp4','wmv','mov','mpg','mpeg','3gp','flv']
valid_extension_modifiers = ['!ut','part','rar','zip']

known_release_groups = ['YTS','LOL','killers','ASAP','dimension','ETRG','rarbg','fum','ift','2HD','FoV','FQM','DONE','vision','fleet'
,'Yify','MrLss','fever','p0w4','TLA','refill','notv','reward','bia','maxspeed','FiHTV','BATV','SickBeard','sfm']

# garbage is ignored from filenames
garbage = ['Unrated', 'DC', 'Dual', 'VTV', 'ag', 'esubs', 'eng', 'subbed', 'artsubs', 'sample', 'ExtraTorrentRG', 'StyLish', 'Release', 'Internal', '2CH' ]

# undesired wordslowers the confidence weight if detected
undesired = ['.HI.', '.Impaired.', '.Comentários.', '.Comentarios.' ]

# video_quality, video_size and release_groups should agree between movie file and subtitles, otherwise weight is reduced
video_quality = ['HDTV', 'PDTV', 'XviD', 'DivX', 'x264', 'aac', 'dd51', 'webdl', 'webrip', 'BluRay', 'blueray', 'BRip', 'BRRip', 'BDRip', 'DVDrip', 'DVD', 'AC3', 'DTS', 'TS', 'R5', 'R6', 'DVDScr', 'PROPER', 'REPACK' ]
video_size = ['480', '540', '720', '1080']                              
    

####### Dragons ahead !! #######

Done = False


import os, sys, traceback
import json, re
import shutil, stat, glob, filecmp, tempfile
import signal, platform
import threading, time, random


from zipfile import ZipFile

if(platform.system().lower().find("windows") > -1):
    if Debug > 2:
        print('Windows system detected')
    import msvcrt
    getch = msvcrt.getch

    def winHardLink(source, link_name):
        import ctypes
        ch1 = ctypes.windll.kernel32.CreateHardLinkW
        ch1.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
        ch1.restype = ctypes.c_ubyte
        if not ch1(link_name, source, 0):
            raise ctypes.WinError()
    os.link = winHardLink
    
    def winSymLink(source, link_name):
        import ctypes
        csl = ctypes.windll.kernel32.CreateSymbolicLinkW
        csl.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
        csl.restype = ctypes.c_ubyte
        flags = 0
        if source is not None and os.path.isdir(source):
            flags = 1
        if not csl(link_name, source, flags):
            raise ctypes.WinError()
    os.symlink = winSymLink
else:
    if Debug > 2:
        print('Unix system detected')
    import sys, tty
    #fd = sys.stdin.fileno()
    #if not os.isatty(sys.stdin.fileno()):
    #    # Cron Mode
    tty.setraw(sys.stdin.fileno())
    getch = sys.stdin.read(1)


REQUIREMENTS = [ 'future', 'requests' , 'beautifulsoup4', 'rarfile' ]

try:
    from future.utils import iteritems
    import requests
    from bs4 import BeautifulSoup
    from rarfile import RarFile
    from queue import Queue, Empty
except (Exception) as e:
    print('! Missing requirements. '+str(type(e)))
    import os, pip
    pip_args = [ ]
    # pip_args = [ '-vvv' ]
    if 'http_proxy' in os.environ:
        proxy = os.environ['http_proxy']
        if proxy:
            pip_args.append('--proxy')
            pip_args.append(proxy)
    pip_args.append('install')
    for req in REQUIREMENTS:
        pip_args.append( req )
    print('Installing: ' + str(REQUIREMENTS))
    pip.main(pip_args)
    # pip.main(initial_args = pip_args)
 
    # try to import again
    try:
        from future.utils import iteritems
        import requests
        from bs4 import BeautifulSoup
        from rarfile import RarFile
        from queue import Queue, Empty
        print('Sucessfully installed the required libraries\n')
    except (Exception) as e:
        print('\nPython modules needed: ' + str(REQUIREMENTS))
        print('We failled to install them automatically: '+str(type(e)))
        print('! Traceback:')
        traceback.print_exc(file=sys.stdout)
        print()
        print('\nTry running this with Admin Priviliges, or')
        print('Run in a command prompt Admin Priviliges:\n')
        print('pip install requests beautifulsoup4 rarfile')
        print('\nPress any key to exit...')
        if Debug > -1:
            junk = getch()
        sys.exit('Unmet dependencies: requests beautifulsoup4 rarfile')



def signal_handler(signal, frame):
    global videosQ, Done
    Done=True
    videosQ.queue.clear()
    print('Cleared List. Terminating in 5s')
    time.sleep(5)
    sys.exit('User ordered a termination')
signal.signal(signal.SIGINT, signal_handler)



lock = threading.Lock()
local = threading.local()
local.output = ''
local.wanted_languages = []




if ltv_username is "USERNAME":
    print('\nPlease edit ltv-downloader.py file and configure with your LTV\'s Username and Password...')
    junk = getch()
    sys.exit()


def SameFile(file1, file2):
    try:
        return filecmp.cmp(file1, file2)
        # return os.stat(file1) == os.stat(file2)
    except:
        return False
os.path.samefile = SameFile

def UpdateFile(src, dst):
    if src == dst:
        return True
    exc = ""
    for x in [1, 2, 3]: 
        try:
            if not os.path.isfile(src):
                return False
            
            if not os.path.isfile(dst):
                os.rename(src, dst)
                return True
            
            if os.path.samefile(src, dst):
                os.remove(src)
                return True
            
            if os.path.getsize(src) < 1500 and os.path.getsize(dst) >= 1500:
                os.remove(src)
                return True
                
            if os.path.getsize(dst) < 1500 and os.path.getsize(src) >= 1500:
                os.remove(dst)
                os.rename(src, dst)
                return True
                
            if os.path.getmtime(src) < os.path.getmtime(dst):
                os.remove(src)
                return True
                
            if os.path.getmtime(dst) < os.path.getmtime(src):
                os.remove(dst)
                os.rename(src, dst)
                return True
            
            if os.path.getsize(src) < os.path.getsize(dst):
                os.remove(src)
                return True
                
            if os.path.getsize(dst) < os.path.getsize(src):
                os.remove(dst)
                os.rename(src, dst)
                return True
            
            os.remove(dst)
            os.rename(src, dst)
            return True
            
        except (Exception) as e:
            exc = e
            time.sleep(0.1)
            pass
    
    print('\nSomething went wrong renaming files: '+str(type(exc))+'\n'+src+'\nto:\n'+dst)
    return False

def stringify(input):
    if isinstance(input, dict):
        return {stringify(key):stringify(value) for key,value in input.items()}
    elif isinstance(input, list):
        return [stringify(element) for element in input]
    elif isinstance(input, str):
        return input.encode('ascii', 'replace').decode('utf8')
    else:
        return input


## Takes car of everything related to the Website
class LegendasTV:
    
    def __init__(self, ltv_username, ltv_password, download_dir=None):
        if not download_dir:
            download_dir = tempfile.gettempdir()

        self.download_path = os.path.abspath(download_dir)
        self.base_url = 'http://legendas.tv'
        self.username = ltv_username
        self.password = ltv_password
        
        self.login_url = self.base_url+'/login'
        self.logout_url = self.base_url+'/users/logout'
        #self.searh_url = self.base_url+'/busca/'
        self.searh_url = self.base_url+'/util/carrega_legendas_busca/'
        self.download_url = self.base_url+'/downloadarquivo/'
        
        self.session = requests.Session()
        self.session.auth = (ltv_username, ltv_password)
        self.session.headers.update({'User-Agent': 'LegendasTV-Downloader at GitHub'})
        self.session.mount("http://", requests.adapters.HTTPAdapter(max_retries=3))
        
    ## Login in legendas.tv
    def login(self):
        login_data= {'data[User][username]':self.username,'data[User][password]':self.password, '_method':'POST'}
        
        try:
            r = self.session.post(self.login_url, data=login_data, timeout=ltv_timeout)
            r.raise_for_status()
        except (Exception) as e:
            if Debug > -1:
                print('! Error, loging in! '+str(type(e)))
            return False
        
        if "rio ou senha inv" in r.text:
            if Debug > -1:
                print('! Error, wrong login user/pass!')
            return False
        return True

    ## Logout
    def logout(self):
        try:
            r = self.session.get(self.logout_url, timeout=ltv_timeout)
            r.raise_for_status()
        except (Exception) as e:
            if Debug > -1:
                print('! Error, loging out! '+str(type(e)))
            return False
        return True

    ## Search and select best subtitle
    def search(self, originalShow):
        
        if Debug > 2:
            local.output+='------- Searching -------\n'
        if Debug > 2:
            local.output+='ShowName='+str(originalShow['ShowName'])+'\n'
            local.output+='Year='+str(originalShow['Year'])+'\n'
            local.output+='Season='+str(originalShow['Season'])+'\n'
            local.output+='Episode='+str(originalShow['Episode'])+'\n'
            local.output+='Group='+str(originalShow['Group'])+'\n'
            local.output+='Quality='+str(originalShow['Quality'])+'\n'
            local.output+='Size='+str(originalShow['Size'])+'\n'
            local.output+='Undesired='+str(originalShow['Undesired'])+'\n'
            local.output+='Unknown='+str(originalShow['Unknown'])+'\n'
            local.output+='\n'
        
        list_possibilities = []

        for iTry in 1,2,3:
            if len(list_possibilities) > 0:
                break
            vsearch_array = []

            if originalShow['Season'] and originalShow['Episode']:
                if iTry == 1:
                    if len(originalShow['Episode'])>1:
                        vsearch_array.append(' '.join(originalShow['ShowName'])+' '+"S{:02d}E".format(originalShow['Season'][0]) + "E".join('{:02d}'.format(a) for a in originalShow['Episode']))
                    vsearch_array.append(' '.join(originalShow['ShowName'])+' '+"S{:02d}E{:02d}".format(originalShow['Season'][0], originalShow['Episode'][0]))
                
                if iTry == 2:
                    if len(originalShow['Episode'])>1:
                        vsearch_array.append(' '.join(originalShow['ShowName'])+' '+"{:0d}x".format(originalShow['Season'][0]) + "x".join('{:02d}'.format(a) for a in originalShow['Episode']))
                    vsearch_array.append(' '.join(originalShow['ShowName'])+' '+"{:0d}x{:02d}".format(originalShow['Season'][0], originalShow['Episode'][0]))

                if iTry == 3:
                    vsearch_array.append(' '.join(originalShow['ShowName'])+' '+"{:0d}{:02d}".format(originalShow['Season'][0], originalShow['Episode'][0]))
                    ##vsearch_array.append(' '.join(originalShow['ShowName'])+' '+"{:0d} {:02d}".format(originalShow['Season'][0], originalShow['Episode'][0]))
                
            else:
                if iTry == 1:
                    if originalShow['Group'] and originalShow['Year']:
                        vsearch_array.append(' '.join(originalShow['ShowName'])+' '+originalShow['Group'][0]+' '+originalShow['Year'][0])
                    
                if iTry == 2:
                    if originalShow['Year']:
                        vsearch_array.append(' '.join(originalShow['ShowName'])+' '+originalShow['Year'][0])
                        
                    if originalShow['Group']:
                        vsearch_array.append(' '.join(originalShow['ShowName'])+' '+originalShow['Group'][0])
                    
                if iTry == 3:
                    vsearch_array.append(' '.join(originalShow['ShowName']))


            ## Search 6 pages and build a list of possibilities
            for vsearch in vsearch_array:
                
                # vsearch = urllib.parse.quote(vsearch)
                for vsearch_prefix in ['/-/-', '/-/-/2', '/-/-/3', '/-/-/4', '/-/-/5', '/-/-/6']:
                    newPossibilities = 0
                    
                    if Debug < 2:
                        local.output+='. '
                    else:
                        local.output+="\nSearching for subtitles with: "+vsearch+" , "+vsearch_prefix+'\n'
                    
                    url = self.searh_url + vsearch + vsearch_prefix
                    try:
                        r = self.session.get(url, timeout=ltv_timeout)
                        r.raise_for_status()
                    except (Exception) as e:
                        if Debug > -1:
                            local.output+='! Error Searching 3 times! '+str(type(e))+'\n'
                            local.output+=url+'\n'
                        with lock:
                            statistics['Failed'] += 1
                        return False
                        
                    soup = BeautifulSoup(r.text, "html.parser")

                    div_results = soup.find('div',{'class':'gallery clearfix list_element'})
                    if div_results:
                        div_results = div_results.findAll('article',recursive=False)
                    if not div_results:
                        if Debug > 2:
                            local.output+='No results\n'
                        break
                    
                    for span_article in div_results:
                        span_results = span_article.findAll('div',recursive=False)

                        if not span_results:
                            if Debug > 2:
                                local.output+='No results\n'
                            continue

                        for span in span_results:

                            try:
                                td = span.find('a').get('href')
                                subName = span.find('a').contents[0]

                                flag = span.find('img').get('src')
                            except:
                                if Debug > 1:
                                    local.output+="! Error parsing result list: "+span.prettify()+'\n'
                                continue

                            if not td:
                                if Debug > 2:
                                    local.output+='#### Something went wrong ####\n'
                                continue
                            
                            # Parse the link
                            tmpregex = re.search('/download/([^/\\\]+)/([^/\\\]+)/([^/\\\]+)',td)

                            if not tmpregex or tmpregex.lastindex<3:
                                local.output+='#### Error parsing link:'+td+' ####\n'
                                continue
                                
                            # Get the download ID
                            download_id = tmpregex.group(1)
                            release = tmpregex.group(3)

                            if not download_id or not release:
                                if Debug > 2:
                                    local.output+='Couldn\'t get download_id and Release\n'
                                continue
                            
                            if download_id in [x['id'] for x in list_possibilities]:
                                ## Already listed this
                                continue
                            
                            ## Get the language
                            tmpregex = re.search('/[a-zA-Z0-9]*/(?:icon|flag)_([a-zA-Z0-9]+)\.(gif|jpg|jpeg|png)',flag)
                            
                            if not tmpregex or tmpregex.lastindex<2:
                                local.output+='#### Error parsing flag: '+flag+' ####\n'
                                continue
                            language = tmpregex.group(1)
                            
                            
                            possibility = {}
                            possibility.clear()
                            
                            newPossibilities += 1
                            
                            possibility['%'] = 100

                            possibility['id'] = download_id
                            
                            possibility['release'] = release.lower()
                            
                            possibility['sub_name'] = subName.lower()
                            
                            if 'pt' in language:
                                possibility['language'] = 'pt'
                            elif 'braz' in language:
                                possibility['language'] = 'br'
                            elif 'usa' in language:
                                possibility['language'] = 'en'
                            else:
                                if Debug > 2:
                                    local.output+='Couldn\'t get Language\n'
                                continue
                            
                            # Filter wanted_languages
                            if possibility['language'] not in preferred_languages:
                                if Debug > 2:
                                    local.output+='0!!, Wrong language: '+possibility['language']+', from: '+str(preferred_languages)+'\n'
                                continue
                                
                            #downloads = td.contents[5]
                            #possibility['downloads'] = downloads.lower()
                            
                            #comments = td.contents[7]
                            #possibility['comments'] = comments.lower()
                            
                            #rating = td.contents[8].contents[1]
                            #possibility['rating'] = rating.lower()
                            
                            #uploader = td.parent.find('a').contents[0]
                            #possibility['uploader'] = uploader
                            
                            #date = span.findAll('td')[2].contents[0]
                            #possibility['date'] = date.lower()
                            
                            if Debug > 2:
                                local.output+='\nFOUND!: '+possibility['language']+' - '+possibility['release']+'\n'
                            
                            
                            releaseShow = parseFileName(possibility['release'])
                            
                            subnameShow = parseFileName(possibility['sub_name'])
                            
                            releaseShow['ShowName'] = list(set(releaseShow['ShowName'] + subnameShow['ShowName']))
                            releaseShow['Year'] = list(set(releaseShow['Year'] + subnameShow['Year']))
                            releaseShow['Season'] = list(set(releaseShow['Season'] + subnameShow['Season']))
                            releaseShow['Episode'] = list(set(releaseShow['Episode'] + subnameShow['Episode']))
                            releaseShow['Group'] = list(set(releaseShow['Group'] + subnameShow['Group']))
                            releaseShow['Quality'] = list(set(releaseShow['Quality'] + subnameShow['Quality']))
                            releaseShow['Size'] = list(set(releaseShow['Size'] + subnameShow['Size']))
                            releaseShow['Undesired'] = list(set(releaseShow['Undesired'] + subnameShow['Undesired']))
                            releaseShow['Unknown'] = list(set(releaseShow['Unknown'] + subnameShow['Unknown']))
                            
                            possibility['%'] = calculateSimilarity(originalShow, releaseShow)
                            
                            if not download_each_lang:
                                langindex = preferred_languages.index(possibility['language'])
                                if Debug > 2:
                                    local.output+='-'+str(langindex*21)+', Language '+possibility['language']+' at pos '+str(langindex)+'\n'
                                possibility['%'] -= 21*langindex
                            
                            list_possibilities.append(possibility)

                    if Debug > 2:
                        local.output+='Got results: '+str(newPossibilities)+'\n'

                    ## If this result page was not full, don't read the next one
                    if newPossibilities < 20:
                        break

        if not list_possibilities:
            if Debug > 2:
                local.output+='No subtitles found\n'
            with lock:
                statistics['NoSubs'] += 1
            return False

        if Debug > 2:
            local.output+='------------------\n'
        final_list = sorted(list_possibilities, key=lambda k: k['%'], reverse=True)
        
        for idx, possibility in enumerate(final_list):
            if Debug > 1:
                local.output+='Chance '+str(idx)+', '+str(possibility['%'])+'%, '+possibility['language']+', '+possibility['release'] + ' | ' + possibility['sub_name'] +'\n'
        
        if final_list[0]['language'] not in local.wanted_languages:
            if Debug > 2:
                local.output+='\n-- Best subtitle already present --\n\n'
            with lock:
                statistics['NoBest'] += 1
            return False
        
        return final_list[0]

    ## Downloads a subtitle given it's ID
    def download(self, subtitle):
        
        download_id = subtitle['id']
        if download_id:
            url_request = self.download_url+download_id
            if Debug == 0:
                local.output+='Download'
            if Debug > 2:
                local.output+='\n------- Downloading -------\n'
                local.output+='Downloading '+subtitle['language']+', '+subtitle['release']+'\n'
            
            try:
                r = self.session.get(url_request, timeout=ltv_timeout*4)
                
                # print("\nurl:\n"+str(r.url))
                # print("\nrequested headers:\n"+str(r.request.headers))
                # print("\nheaders:\n"+str(r.headers))
                # print("\ncookies:\n"+str(r.cookies))
                
                r.raise_for_status()
            except (Exception) as e:
                if Debug > 1:
                    local.output+='! Error downloading! '+str(type(e))+'\n'
                return False
            
            legenda = r.content
            
            localName = ""
            if 'Content-Disposition' in r.headers and "filename=" in r.headers['Content-Disposition']:
                # If the response has Content-Disposition, we take file name from it
                localName = r.headers['Content-Disposition'].split('filename=')[1]
                if localName[0] == '"' or localName[0] == "'":
                    localName = localName[1:-1]
            
            if len(localName)>4:
                self.archivename= os.path.join(self.download_path, str(localName))
            else:
                self.archivename = os.path.join(self.download_path, str(download_id))
            
            if r.url.endswith('.rar') or ('Content-Type' in r.headers and 'rar' in r.headers['Content-Type']):
                self.archivename += '.rar'
            elif r.url.endswith('.zip') or ('Content-Type' in r.headers and 'zip' in r.headers['Content-Type']):
                self.archivename += '.zip'
            elif r.url.endswith('.srt') or ('Content-Type' in r.headers and 'srt' in r.headers['Content-Type']):
                if Debug > -1:
                    local.output+='Downloaded an .SRT. Are you logged in?\n'
                return False
            else:
                if Debug > 2:
                    local.output+='No download MIME TYPE. Not forcing extension\n'
            if Debug > 2:
                local.output+=' Downloaded :'+self.archivename+'\n'

            f = open(self.archivename, 'wb')
            f.write(legenda)
            #pickle.dump(legenda, f)
            f.close()
            if Debug > 2:
                local.output+='Subtitle downloaded with sucess!\n'
            return True

    ## Choose the likeliest and extracts it
    def extract_sub(self, dirpath, originalFilename, originalShow, language):
        global lock
                
        if Debug > 2:
            local.output+='\n------- Extracting -------\n'
        if Debug > 3:
            local.output+='File: '+self.archivename+'\n'
        if Debug > 2:
            local.output+="Extracting a "
        try:
            archive = ZipFile(self.archivename)
            if Debug > 2:
                local.output+='zip file...\n'
        except:
            try:
                archive = RarFile(self.archivename)
                if Debug > 2:
                    local.output+='rar file...\n'
            except:
                if self.archivename.endswith(tuple(valid_subtitle_extensions)):
                    if Debug > -1:
                        local.output+='\n! Error! Downloaded file was not an archive: '+self.archivename+'\n'
                else:
                    if Debug > -1:
                        local.output+='\n! Error! Opening archive: '+self.archivename+'\n'
                        local.output+='UNRAR must be available on console\n'
                        
                if os.path.getsize(self.archivename) < 1500:
                    fp = open(self.archivename, "r")
                    content = fp.read()
                    fp.close()
                    if Debug > -1:
                        local.output+='\n! Small file, content: '+content+'\n'
                
                with lock:
                    statistics['Failed'] += 1
                return False

        language_compensation = 0
        if not download_each_lang:
            langindex = -1
            langindex = local.wanted_languages.index(language)
            if langindex>=0:
                language_compensation = 21*langindex
            else:
                local.output+='No language? '+language+'\n'

        files = archive.infolist()
            
        if Debug > 2:
            local.output+='Files in Archive: ' + str(files)+'\n'

        srts = []
        current_maxpoints = 0
        best_rarfile = []

        for current_rarfile in files:
            
            testname = current_rarfile.filename.lower()
            testname = os.path.basename(str(testname))
            
            if not testname.endswith(tuple(valid_subtitle_extensions)+('rar', 'zip')):
                if Debug > 2:
                    local.output+='Non Sub file: ' + str(current_rarfile)+'\n'
                continue
            
            if Debug > 2:
                local.output+='\n--- Analyzing: '+str(testname)+'\n'
            
            compressedShow = parseFileName(testname)
            
            points = calculateSimilarity(originalShow, compressedShow)
            
            points = points - language_compensation
            
            if Debug > 2:
                local.output+='Adding subtitle file with '+str(points)+'% : '+str(testname)+'\n'
            
            if current_maxpoints<points:
                current_maxpoints = points
                best_rarfile = current_rarfile

        if Debug > 2:
            local.output+='-------\n'

        if not best_rarfile or current_maxpoints<1:
            if Debug > -1:
                local.output+='! Error: No valid subs found on archive\n'
            with lock:
                statistics['Failed'] += 1
            return False

        extract = []
        
        extract.append(best_rarfile)

        # maximum=confidence_threshold
        # for idx, [p, n] in enumerate(srts):
        #     print "Result %d, %d%%: %s" % (idx, p, n.filename)
        #     if p >= maximum:
        #         maximum = p
        #         extract.append(n)
            
        ## Extracting
        for fileinfo in extract:
            dest_filename = os.path.basename(fileinfo.filename) # This prevents from extracting from sub-folders
            # fileinfo.filename = os.path.basename(fileinfo.filename) # This prevents from extracting from sub-folders
            
            if Debug > 2:
                local.output+='Extracted '+dest_filename+' with ' +str(current_maxpoints+language_compensation)+'%\n'

            if dest_filename.endswith(('rar', 'zip')):
                if Debug > 2:
                    local.output+='Recursive extract, RAR was inside: '+fileinfo.filename+'\n'
                archive.extract(fileinfo, self.download_path)
                self.archivename = os.path.join(self.download_path, fileinfo.filename)
                if not ltv.extract_sub(dirpath, originalFilename, group, size, quality, language):
                    return False
                continue
            
            if len(extract) == 1 and rename_subtitle:
                dest_filename = os.path.splitext(originalFilename)[0] + os.path.splitext(dest_filename)[1]
            
            if append_language:
                dest_filename = os.path.splitext(dest_filename)[0]+'.'+language+os.path.splitext(dest_filename)[1]
                
            if append_confidence:
                dest_filename = os.path.splitext(dest_filename)[0]+'.'+str(current_maxpoints+language_compensation)+os.path.splitext(dest_filename)[1]
            
            if Debug > 2:
                local.output+='Extracting subtitle as: '+dest_filename+'\n'
            dest_fullFilename = os.path.join(dirpath, dest_filename)
            
            try:               
                fileContents = archive.read(fileinfo)
                
                f = open(dest_fullFilename, 'wb')
                f.write(fileContents)
                f.close()
                
                if Debug > 2:
                    local.output+='Subtitle saved with sucess in: '+dirpath+'!\n'
                with lock:
                    statistics['DL'] += 1
                    if not local.wanted_languages == preferred_languages:
                        statistics['Upg'] += 1
                    if language == local.wanted_languages[0]:
                        statistics['Best'] += 1
                    else:
                        statistics['NoBest'] += 1
                    if language == 'pt':
                        statistics['PT'] += 1
                    elif language == 'br':
                        statistics['BR'] += 1
                    elif language == 'en':
                        statistics['EN'] += 1
            
            except (Exception) as e:
                with lock:
                    statistics['Failed'] += 1
                if Debug > 0:
                    local.output+='! Error, decrompressing! '+str(type(e))+'\n'
                elif Debug > -1:
                    local.output+='! Error, decrompressing!\n'

            if clean_old_language:
                tmp = os.path.splitext(os.path.join(dirpath, originalFilename))[0] + '.??.s*'
                for tmp2 in glob.glob(re.sub(r'(?<!\[)\]', '[]]', re.sub(r'\[', '[[]', tmp))):
                    if Debug > 2:
                        local.output+='Found: '+tmp2+'\n' 
                    if os.path.samefile(dest_fullFilename, tmp2):
                        continue
                    if Debug > 2:
                        local.output+='Deleted old language: '+os.path.basename(tmp2)+'\n'
                    os.remove(tmp2)

            ## Create hard/SymLink with the same name as the video, for legacy players
            if hardlink_without_lang_to_best_sub and ( not rename_subtitle or append_language):
                createLinkSameName(Folder=dirpath, Movie=originalFilename, Destination=dest_filename)

        return True
        
def moveMedia(src, dst):
    dstFolder = os.path.dirname(dst)
    
    scrFileName = os.path.splitext(os.path.basename(src))[0]
    dstFileName = os.path.splitext(os.path.basename(dst))[0]
    
    # Moving main video file
    if UpdateFile(src, dst):
        if Debug > 1:
            local.output+='Moved ' + os.path.basename(src) + ' to: '+os.path.basename(dstFolder)+'\n'
    else:
        if Debug > 1:
            local.output+='! Error renaming. File in use? '+filename+'\n'
        return False
    
    
    # Moving related subtitles
    sub_pattern = re.sub(r'(?<!\[)\]', '[]]', re.sub(r'\[', '[[]', os.path.splitext(src)[0]+'.*'))
    for tmpFile in glob.glob(sub_pattern):
        if not os.path.splitext(tmpFile)[1][1:] in valid_subtitle_extensions:
            if Debug > 2:
                local.output+='Not a valid extension: '+os.path.splitext(tmpFile)[1][1:]+'\n'
            continue
        if Debug > 1:
            local.output+='File found to move: '+tmpFile+'\n'
        newFile = os.path.basename(tmpFile).replace(scrFileName, dstFileName)
        newFullPath = os.path.join(dstFolder, newFile)
        if Debug > 1:
            local.output+='Renaming to: '+newFile+'\n'
        
        if not UpdateFile(tmpFile, newFullPath):
            if Debug > -1:
                local.output+='! Error recovering subtitle from ETTV folder! '+tmpFile+'\n'
        else:
            if Debug > -1:
                local.output+='Recovered 1 subtitle from ETTV folder: '+newFile+'\n'
        
    return True
    
def checkAndDeleteFolder(src):
    # Search for subtitles or media files
    
    for files in os.listdir(src):
        if Debug > 2:
            local.output+='File found: '+files+' with ext: '+os.path.splitext(files)[1][1:]+'\n'
        if files in ['RARBG.COM.mp4','RARBG.mp4']:
            continue
        if os.path.splitext(files)[1][1:] in [x for x in valid_subtitle_extensions if x != 'txt']:
            return False
        if os.path.splitext(files)[1][1:] in valid_video_extensions:
            return False
        if os.path.splitext(files)[1][1:] in valid_extension_modifiers:
            return False
        # os.remove(os.path.join(src,files))
    
    if Debug > 1:
        local.output+='Parent folder is empty. Removed!\n'
        
    def del_rw(action, name, exc):
        os.chmod(name, stat.S_IWRITE)
        local.output+='Had to fix permissions to delete file: '+name+'\n'
        os.remove(name)
        os.removedirs(name)
    shutil.rmtree(src, onerror=del_rw)
    # os.rmdir(src)
    return True
    
# Remove garbage from filenames
def cleanAndRenameFile(Folder, filename):

    # Generate Regex
    regex = '(' + '|'.join(clean_name_from)+')'

    if not re.search('[^a-zA-Z0-9\-]+'+regex+'[^a-zA-Z0-9\-]', filename, re.I):
        return filename
    
    statementClean = re.compile('[^a-zA-Z0-9\-]+'+regex+'[\]\)\}]?', re.I)
    newname = statementClean.sub('', filename)

    fullFilename = os.path.join(Folder, filename)
    fullNewname = os.path.join(Folder, newname)

    # Sanity check
    if fullFilename == fullNewname:
        if Debug > 2:
            local.output+='Error cleaning original name\n'
        return filename

    # Cleaning video file
    if UpdateFile(fullFilename, fullNewname):
        if Debug > -1:
            local.output+='Renamed to: '+newname+'\n'
    else:
        if Debug > 2:
            local.output+='! Error renaming. File in use? '+filename+'\n'
        return filename
    
    # Cleaning related subtitles and other files with different extensions
    sub_pattern = re.sub(r'(?<!\[)\]', '[]]', re.sub(r'\[', '[[]', os.path.splitext(fullFilename)[0]+'.*'))
    for tmpFile in glob.glob(sub_pattern):
        tmpNew = statementClean.sub('', tmpFile)
        if tmpNew != tmpFile:
            if UpdateFile(tmpFile, tmpNew):
                if Debug > -1:
                    local.output+='Renamed sub to: '+tmpNew+'\n'
            else:
                if Debug > -1:
                    local.output+='! Error renaming subtitles: '+tmpFile+'\n'
        
    return newname


# Fix ETTV folders
def cleanAndMoveFromSubfolder(origFolder, origFilename):
    shouldMove = False
    
    # Generate Regex
    regex = '(' + '|'.join(clean_name_from)+')'

    statementClean = re.compile('[^a-zA-Z0-9\-]+'+regex+'[\]\)\}]?', re.I)

    origAbsoluteFile = os.path.join(origFolder, origFilename)
    
    parentFolder = os.path.basename(origFolder)
    grandParentFolder = os.path.dirname(origFolder)
    
    if not os.path.lexists(grandParentFolder):
        return (origFolder, origFilename)
    
    cleanParentFolder = statementClean.sub('', parentFolder)
    cleanFilename = statementClean.sub('', origFilename)
    fileExt = os.path.splitext(cleanFilename)[1]
    
    ## If file and folder have the same full name, move
    if cleanParentFolder == os.path.splitext(cleanFilename)[0]:
        if moveMedia(origAbsoluteFile, os.path.join(grandParentFolder, cleanFilename)):
            deleted = checkAndDeleteFolder(origFolder)
            if Debug > -1:
                if deleted:
                    local.output+='ETTV subfolder fixed: '+cleanFilename+'\n'
                else:
                    local.output+='ETTV subfolder fixed, but not yet empty!: '+cleanFilename+'\n'
            return (grandParentFolder, cleanFilename)
        else:
            if Debug > -1:
                local.output+='ETTV subfolder detected, but failed to fix\n'
            return (origFolder, origFilename)
    
    ## If parent has a tv showname, parse its info
    if re.match(".+[^a-zA-Z0-9]S\d\dE\d\d(E\d\d)?[^a-zA-Z0-9].+", cleanParentFolder):
        if Debug > 1:
            local.output+='Father has a TV Show name...'
        try:
            name=re.sub("(.+[^a-zA-Z0-9])S\d\dE\d\d(E\d\d)?[^a-zA-Z0-9].+", '\\1', cleanParentFolder) # Including ending \. (dot)
            season=int(re.sub(".+[^a-zA-Z0-9]S(\d\d)E\d\d(E\d\d)?[^a-zA-Z0-9].+", '\\1', cleanParentFolder))
            episode=int(re.sub(".+[^a-zA-Z0-9]S\d\dE(\d\d)(E\d\d)?[^a-zA-Z0-9].+", '\\1', cleanParentFolder))
        except (Exception) as e:
            if Debug > -1:
                local.output+='Very strange error happened, parsing ETTV folder. Report to programmer please!\n'
            return (origFolder, origFilename)
        
        # Check if son-movie is the corresponding episode
        if ( cleanFilename.lower().startswith((name.lower()+"{:0d}{:02d}").format(int(season), int(episode))) or
            cleanFilename.lower().startswith((name.lower()+"s{:02d}e{:02d}").format(int(season), int(episode))) ):
            destFileName = cleanParentFolder+fileExt
            if Debug > 1:
                local.output+='Son has the same!!\nMoving to: ' + os.path.join(os.path.basename(grandParentFolder), destFileName) + '\n'
            
            # return (origFolder, origFilename)
            if moveMedia(origAbsoluteFile, os.path.join(grandParentFolder, destFileName)):
                deleted = checkAndDeleteFolder(origFolder)
                if Debug > -1:
                    if deleted:
                        local.output+='ETTV subfolder fixed\n'
                    else:
                        local.output+='ETTV subfolder fixed, but not yet empty!\n'
                return (grandParentFolder, destFileName)
            else:
                if Debug > -1:
                    local.output+='ETTV subfolder detected, but failed to fix\n'
                return (origFolder, origFilename)
        else:
            if Debug > 0:
                local.output+='ETTV Parent is different than Son\n'+(name.lower()+"s{:02d}e{:02d}").format(int(season), int(episode))+' VS '+cleanFilename
    else:
        if Debug > 1:
            local.output+='No ETTV subfolder detected, nothing to fix\n'
    return (origFolder, origFilename)

# Create hardlink
def createLinkSameName(Folder, Movie, Destination, HardLink=True):

    Movie = os.path.basename(Movie)
    Destination = os.path.basename(Destination)
    fullDestination = os.path.join(Folder, Destination)

    linkName = os.path.splitext(Movie)[0] + os.path.splitext(Destination)[1]
    fullLinkName = os.path.join(Folder, linkName)
    
    if os.path.samefile(fullDestination, fullLinkName):
        if Debug > 2:
            local.output+='Link without language already exists: \n  '+fullDestination+' = \n  '+fullLinkName+'\n'
        return
    
    try:
        os.remove(fullLinkName)
    except (Exception):
        #if Debug > 2:
        #    print 'Error: Couldn\'t remove %s' % (linkName)
        pass

    try:
        if HardLink:
            os.link(fullDestination, fullLinkName)
        else: # Relative path only when creating symbolic links
            os.symlink(Destination, fullLinkName)

        if Debug > 2:
            local.output+='Linked: '+linkName+' --> '+Destination+'\n'
    except (Exception):
        if Debug > 2:
            local.output+='! Error linking '+linkName+' --> '+Destination+'\n'
            local.output+='! print_exc():\n'
            traceback.print_exc(file=sys.stdout)
            print()

    return

def getAppendRating(fullpath, withYear=True, search=False, imdbID=0):
    global count, Debug
    fullFilename = os.path.abspath(fullpath)
    dirpath, foldername = os.path.split(fullFilename)

    changed = False

    tmpregex = re.search('([^\(\)\[\]]+)(?:\((\d{4})(?:\-\d{2,4})?\))\ ?(?:\[([\d\.]+)\])?',foldername)

    # Only process movie folder names with year
    if tmpregex is None or tmpregex.lastindex<2:
        if Debug>0:
            print("No movie folder: "+foldername)
        return fullFilename

    # if count>25:
    #     print('Too much iMDB-Ratings. Sleeping 2 minutes')
    #     time.sleep(110)
    # count+=1
        
    year = ''
    rating= ''
    # Get the download ID
    movie = tmpregex.group(1).strip()
    # if search:
    #     movie = movie.replace(" and ", " ")
    #     movie = movie.replace(" at ", " ")
        
    year = tmpregex.group(2).strip()
    if len(year) <= 1:
        withYear = False

    if tmpregex.lastindex>2:
        rating = tmpregex.group(3).strip()

    payload = {}           
            
    if imdbID:
        payload['i'] = imdbID
        # data = urllib.parse.urlencode({"i":imdbID})
        
    else:
        if withYear:
            payload['y'] = year
        if search:
            payload['s'] = movie
        else:
            payload['t'] = movie
    
    payload['type'] = "movie"

    url = 'http://www.omdbapi.com'
    

    if Debug > 0:
        print('Searching for: '+url + ", " + str(payload))
        
    try:
        
        tmpsession = requests.Session()
        tmpsession.headers.update({'User-Agent': 'LegendasTV-Downloader at GitHub'})
        tmpsession.mount("http://", requests.adapters.HTTPAdapter(max_retries=3))
        
        r = tmpsession.get(url, params=payload, timeout=ltv_timeout*1.5)
        
        r.raise_for_status()
    except (Exception) as e:
        if Debug > 0:
            print('! Error getting imdb rating: '+str(type(e))+'')
        return fullpath

    the_page = r.text
    
    data = json.loads(the_page)
    data = stringify(data)
    
    if Debug > 0:
        print('Got imdb: '+str(data))
        
    if search:
        if 'Search' in data.keys():
            data["Search"] = [item for item in data["Search"] if item["Type"]=="movie"]
            
            if len(data["Search"])==1 and 'imdbID' in data["Search"][0].keys():
                if Debug > -1:
                    print("Found the movie: " + data["Search"][0]["Title"] + " ID:" + data["Search"][0]["imdbID"])
                return getAppendRating(fullpath, True, False, data["Search"][0]["imdbID"])
            else: 
                print("Multiple movies found with similar name: " + foldername)
                return fullFilename
        elif withYear:
            if Debug > 0:
                print("No movies found. Searching without year")
            return getAppendRating(fullpath, False, True, 0)
        
        print("No movie found while searching for: " + foldername)
        return fullFilename
        
    
    if not 'Year' in data.keys() or '/' in data["Year"]:
        if Debug > 0:
            print("No exact movie found. Searching")
        return getAppendRating(fullpath, True, True, 0)
        # if withYear:
        #     print("No rating found. Searching without year")
        #     return getAppendRating(fullpath, False)
        # print("No rating found for: " + foldername + ". The folder name must be wrong")
        # return fullFilename

    if year != data["Year"]:
        print("Year wrong in: " + movie + " " + year + ", found " + data["Year"])
        if imdbID:
            year = data["Year"]
            changed = True
        else:
            return getAppendRating(fullpath, True, True, 0)
        #year = data["Year"]
        #changed = True

    if 'imdbRating' in data.keys() and not '/' in data["imdbRating"]:
        if rating != data["imdbRating"]:
            print("Rating changed for: " + movie + ", " + rating + " to " + data["imdbRating"])
            rating = data["imdbRating"]
            changed = True
        else:
            if Debug > 0:
                print("Rating didn't change for: " + foldername)
    else:
        if Debug > -1:
            print("No rating for this movie: " + str(data))

    if changed:
        newName = movie
        if len(year) > 1:
            newName = newName + " ("+year+")"
        if len(rating) > 1:
            newName = newName + " ["+rating+"]"

        newFullPath = os.path.abspath(os.path.join(dirpath, newName))

        try:
            os.rename(fullFilename, newFullPath)
        except (Exception):
            pass


        if not os.path.isdir(newFullPath):
            if Debug > -1:
                print("Error renaming imdb. File in use? " + newName)
            return fullFilename
        else:
            if Debug > 0:
                print("Renamed with imdb rating: " + newName)
            return newFullPath
    else:
        print("Rating didn't change for: " + foldername + " = " + rating)
    return fullFilename

# Normalize usual video tags for easier comparison
def normalizeTags(tag):
    tag = tag.lower()
    if tag in ['bluray', 'brrip', 'blueray', 'brip', 'bdrip']:
        return 'bluray'
    if tag in ['dvdrip', 'dvd', 'sd']:
        return 'dvd'
    if tag in ['webrip', 'webdl']:
        return 'webdl'
    if tag in ['hdtv', 'pdtv']:
        return 'hdtv'

    if tag in ['x264', 'h264']:
        return 'x264'

    if tag in ['480', '480p', '480i']:
        return '480p'
    if tag in ['540', '540p', '540i']:
        return '540p'
    if tag in ['720', '720p', '720i']:
        return '720p'
    if tag in ['1080', '1080p', '1080i']:
        return '1080p'

    if tag in ['proper', 'repack']:
        return 'repack'

    if tag in ['directors', 'dircut']:
        return 'directors'
    return tag

def fixTags(filename):
    filename=re.sub("[^a-zA-Z0-9](h|x)[^a-zA-Z0-9]264[^a-zA-Z0-9]", '.x264.', filename)

    filename=re.sub("[^a-zA-Z0-9]hd[^a-zA-Z0-9]tv[^a-zA-Z0-9]", '.hdtv.', filename)
    filename=re.sub("[^a-zA-Z0-9]web[^a-zA-Z0-9]dl[^a-zA-Z0-9]", '.webdl.', filename)
    filename=re.sub("[^a-zA-Z0-9]web[^a-zA-Z0-9]rip[^a-zA-Z0-9]", '.webrip.', filename)
    filename=re.sub("[^a-zA-Z0-9]dvd[^a-zA-Z0-9]rip[^a-zA-Z0-9]", '.dvdrip.', filename)
    filename=re.sub("[^a-zA-Z0-9]b(d|r)?[^a-zA-Z0-9]rip[^a-zA-Z0-9]", '.brrip.', filename)

    filename=re.sub("[^a-zA-Z0-9]dd5[^a-zA-Z0-9]1[^a-zA-Z0-9]", '.dd51.', filename)

    filename=re.sub("[^a-zA-Z0-9](en?|it|fr|es)[^a-zA-Z0-9]subs[^a-zA-Z0-9]", '.esubs.', filename)
    return filename

def parseFileName(filename, isShow=False):
    
    detected={'ShowName':[], 'Year':[], 'Season':[], 'Episode':[], 'Group':[], 'Quality':[], 'Size':[], 'Undesired':[], 'Unknown':[]}
    
    # Start analyzis per-se
    filename = filename.lower()
    filename = fixTags(filename)
    
    search_string = re.split('[^a-zA-Z0-9]', filename)

    # Removing empty strings
    search_string = [ st for st in search_string if st ]

    # Removing Extensions
    if search_string[-1] in valid_extension_modifiers:
        search_string.pop()
    if search_string[-1] in valid_video_extensions:
        search_string.pop()
    if search_string[-1] in valid_subtitle_extensions:
        search_string.pop()
    if search_string[-1] in valid_extension_modifiers:
        search_string.pop()
    if search_string[-1] in valid_video_extensions:
        search_string.pop()
    if search_string[-1] in valid_subtitle_extensions:
        search_string.pop()

    # Removing Garbage
    #for idx, val in reversed(list(enumerate(search_string))):
    #     if val in garbage:
    #        search_string.pop(idx)
    #        continue
    
    ## To speed up searching for season tag later
    if re.match(".+[^a-zA-Z0-9]s?\d\d[xe]\d\d([xe]\d\d)?.*", filename, re.I):
        standardSeasonFormat=True
    else:
        standardSeasonFormat=False
    
    
    #possibleGroup = search_string[0]
    possibleGroup=""

    endOfName=0
    for item in search_string:
        
        # Found season and episode tag
        if standardSeasonFormat and re.search('[s]?(\d?\d)[xe](\d\d)(?:[xe](\d\d))?',item):
            tmpregex = re.search('[s]?(\d?\d)[xe](\d\d)(?:[xe](\d\d))?',item)
            detected['Season'].append(int(tmpregex.group(1)))
            detected['Episode'].append(int(tmpregex.group(2)))
            if tmpregex.lastindex>2:
                detected['Episode'].append(int(tmpregex.group(3)))
            endOfName = 1
            continue
        
        # Found video resolution tag
        if sizeRegex.match(item):
            detected['Size'].append(normalizeTags(item))
            endOfName = 1
            continue
        
        # Found a 4 digits number, probably Year
        if re.match("^\W?\d\d\d\d\W?$", item):
            detected['Year'].append(item)
            endOfName = 1
            continue

        # Found a 3 digits number
        if len(detected['ShowName'])>0 and not standardSeasonFormat and re.match("^\W?\d\d\d\W?$", item):
            tmpregex = re.search('^\W?(\d)(\d\d)\W?$',item)
            detected['Season'].append(int(tmpregex.group(1)))
            detected['Episode'].append(int(tmpregex.group(2)))
            endOfName = 1
            continue
        
        # Found well-known group
        if item in known_release_groups:
            detected['Group'].append(item)
            endOfName = 1
            continue

        # Found generic quality tag
        if item in video_quality:
            detected['Quality'].append(normalizeTags(item))
            endOfName = 1
            continue

        # Found known garbage
        if item in garbage:
            continue
            
        # Found known garbage
        if item in clean_name_from:
            continue
            
        # Found undesired word
        if item in undesired:
            detected['Undesired'].append(item)
            endOfName = 1
            continue
            
        # 2CDs video found
        if re.match("^\W?cd\d\d?\W?$", item) or re.match("^\W?\dcd\W?$", item):
            detected['Quality'].append('2cd')
            detected['Quality'].append(item)
            endOfName = 1
            continue
        
        if not endOfName:
            detected['ShowName'].append(item)
            # if re.match("^\d$", item): # After a number, consider the rest as Unknown
            #     endOfName = 2
            continue
        
        #if endOfName == 2:
        #    outSubTitle.append(item)
        #    continue
        
        if not detected['Group']: # Last unknown is possibly the release group
            if possibleGroup:
                detected['Unknown'].append(possibleGroup)
            possibleGroup = item
            continue
        
        detected['Unknown'].append(item)
        
    if not detected['Group'] and possibleGroup:
        detected['Group'].append(possibleGroup)
    
    if (not detected['Season'] and len(detected['Year'])>1) or (isShow and not detected['Season'] and detected['Year']):
        item=detected['Year'].pop()
        print(item)
        m = re.match("^\W?(\d\d)(\d\d)\W?$", item)
        detected['Season'].append(int(m.group(1)))
        detected['Episode'].append(int(m.group(2)))
        
    return detected
    
def calculateSimilarity(originalShow, possibleShow):
    similarity=100
    
    if Debug > 1:
        local.output+='Processing Release:\n'
        local.output+='ShowName='+str(possibleShow['ShowName'])+'\n'
        local.output+='Year='+str(possibleShow['Year'])+'\n'
        local.output+='Season='+str(possibleShow['Season'])+'\n'
        local.output+='Episode='+str(possibleShow['Episode'])+'\n'
        local.output+='Group='+str(possibleShow['Group'])+'\n'
        local.output+='Quality='+str(possibleShow['Quality'])+'\n'
        local.output+='Size='+str(possibleShow['Size'])+'\n'
        local.output+='Undesired='+str(possibleShow['Undesired'])+'\n'
        local.output+='Unknown='+str(possibleShow['Unknown'])+'\n'
        local.output+='\n'
    
    ### Evaluate name
    # Quickly XOR both name-lists to detect differences
    if (set(originalShow['ShowName']) ^ set(possibleShow['ShowName'])):
        for tmp in [j for j in originalShow['ShowName']]:
            if tmp not in possibleShow['ShowName']:
                if Debug > 2:
                    local.output+='-20, Missing word: '+tmp+' in name: '+str(possibleShow['ShowName'])+'\n'
                similarity -= 20
        # Check for reverse missing names
        for tmp in [j for j in possibleShow['ShowName']]:
            if tmp not in originalShow['ShowName']:
                if Debug > 1:
                    local.output+='-15, Too many words: '+tmp+' in release: '+str(possibleShow['ShowName'])+'\n'
                similarity -= 15
    
    ### Evaluate Year if present
    # Quickly check if there's a common Year and pass on
    if not (set(originalShow['Year']) & set(possibleShow['Year'])):
        if originalShow['Year']:
            if originalShow['Year'][0] not in possibleShow['Year']:
                if possibleShow['Year']:
                    if Debug > 2:
                        local.output+='-15, Wrong Year: '+str(originalShow['Year'][0])+' in: '+str(possibleShow['Year'])+'\n'
                    similarity -= 15
                else:
                    if Debug > 2:
                        local.output+='-8, Missing Year: '+str(originalShow['Year'][0])+'\n'
                    similarity -= 8
            
    ### Evaluate season number in name
    # Quickly check if there's a common Year and pass on
    if (set(originalShow['Season']) ^ set(possibleShow['Season'])):
        if originalShow['Season']:
            if originalShow['Season'][0] not in possibleShow['Season']:
                if Debug > 2:
                    local.output+='-15, Missing Season: '+str(originalShow['Season'])+' in: '+str(possibleShow['Season'])+'\n'
                similarity -= 15
    if (set(originalShow['Episode']) ^ set(possibleShow['Episode'])):
        if originalShow['Episode']:
            if originalShow['Episode'][0] not in possibleShow['Episode']:
                if Debug > 2:
                    local.output+='-10, Missing Episode: '+str(originalShow['Episode'])+' in: '+str(possibleShow['Episode'])+'\n'
                similarity -= 10

    ### Filter group
    # Quickly check if there's a common Group and pass on
    if not (set(originalShow['Group']) & set(possibleShow['Group'])):
        if originalShow['Group']:
            for tmp in [j for j in originalShow['Group']]:
                if tmp not in possibleShow['Group'] and tmp not in possibleShow['Unknown']:
                    if Debug > 1:
                        local.output+="-20, Groups don't match perfectly: "+str(originalShow['Group'])+' to '+str(possibleShow['Group'])+'\n'
                    similarity -= 20
    
    ### Filter size
    # Quickly check if there's a common Size and pass on
    if not (set(originalShow['Size']) & set(possibleShow['Size'])):
        if originalShow['Size']:
            for tmp in [j for j in originalShow['Size']]:
                if tmp not in possibleShow['Size'] and tmp not in possibleShow['Unknown']:
                    if Debug > 1:
                        local.output+="-14, Size doesn't match perfectly: "+str(originalShow['Size'])+' to '+str(possibleShow['Size'])+'\n'
                    similarity -= 14
    
    ### Filter quality
    # Quickly XOR both quality-lists to detect differences
    if (set(originalShow['Quality']) ^ set(possibleShow['Quality'])):
        for tmp in [j for j in originalShow['Quality']]:
            if tmp not in possibleShow['Quality']:
                if Debug > 2:
                    local.output+='-5, Missing quality: '+tmp+' in name: '+str(possibleShow['Quality'])+'\n'
                similarity -= 5
        # Check for reverse missing names
        for tmp in [j for j in possibleShow['Quality']]:
            if tmp not in originalShow['Quality']:
                if Debug > 1:
                    local.output+='-3, Too many qualities: '+tmp+' in release: '+str(possibleShow['Quality'])+'\n'
                similarity -= 3
    
    # Devalue undesired words
    for tmp in possibleShow['Undesired']:
        if Debug > 2:
            local.output+='-2, Undesired word found: '+tmp+'\n'
        similarity -= 2
        
    return similarity

# Threaded function: grab from queue and analyze
def ltvdownloader(videosQ):
    global lock, Done
    local.output = ''
    local.wanted_languages = []

    while not Done:
        try:
            if local.output:
                videosQ.task_done()
                with lock:
                    try:
                        print(local.output)
                        #print('remaining items: '+str(videosQ.qsize()))
                    except (Exception):
                        print(local.output.encode('utf-8','ignore'))
                        pass
                        
            local.output=''
            originalFilename= videosQ.get(False)

            videoTitle=[]
            videoSubTitle=[]
            season=0
            episode=0
            year=0
            quality=[]
            size=''
            group=''

            dirpath=''

            dirpath, originalFilename = os.path.split(os.path.abspath(originalFilename))

            if Debug > -1:
                local.output+='\n'+str(threading.current_thread().getName())+'/'+str(videosQ.qsize())+': '+originalFilename+'\n'

            # Remove garbage of movie name and accompanying files
            if clean_name:
                if fix_ETTV_subfolder:
                    dirpath, originalFilename = cleanAndMoveFromSubfolder(dirpath, originalFilename)
                originalFilename = cleanAndRenameFile(dirpath, originalFilename)
            
            # check already existing subtitles to avoid re-download
            existSubs=[]
            subFound=''
            sublang=''
            
            # Check without language
            tmp = os.path.splitext(os.path.join(dirpath, originalFilename))[0] + '.s*'

            # Escape square brackets in filenames, Glob's fault...
            for subFound in glob.glob(re.sub(r'(?<!\[)\]', '[]]', re.sub(r'\[', '[[]', tmp))):
                existSubs.append(subFound)
                if Debug > 1:
                    local.output+='Found a subtitle: '+subFound+'\n'
                break
            
            local.wanted_languages = preferred_languages[:]
            
            # Check with language
            if append_language:
                for idx, lang in reversed(list(enumerate(local.wanted_languages))):
                    tmp = os.path.splitext(os.path.join(dirpath, originalFilename))[0] + '.'+lang+'.s*'
                    for sublang in glob.glob(re.sub(r'(?<!\[)\]', '[]]', re.sub(r'\[', '[[]', tmp))):
                        existSubs.append(sublang)
                        if Debug > 1:
                            local.output+='Found a \''+lang+'\' subtitle: '+sublang+'\n'
                        if idx<stopSearchWhenExistsLang:
                            local.wanted_languages = []
                        else:
                            local.wanted_languages = local.wanted_languages[0:idx]
                            
            if subFound and not ForceSearch and (not sublang or not os.path.samefile(subFound, sublang)):
                with lock:
                    statistics['Best'] += 1
                if Debug > -1:
                    local.output+='No-language subtitles already present\n'
                continue
            
            ## Create symlink with the same name as the video, for some players that don't support multiple languages
            if append_language and hardlink_without_lang_to_best_sub and (len(local.wanted_languages) != len(preferred_languages)):
                createLinkSameName(Folder=dirpath, Movie=originalFilename, Destination=sublang)
        
            if len(local.wanted_languages) == 0:
                if len(input_string) == 2:
                    if Debug > 2:
                        local.output+='Single argument: Forcing search\n'
                else:
                    with lock:
                        statistics['Best'] += 1
                    if Debug > -1:
                        local.output+='Best-language subtitles already present\n'
                    continue

            ###############################
            
            parsedShow = parseFileName(originalFilename)
            if Debug > 0:
                local.output+='Processed name:\n'
                local.output+='outShowName='+str(parsedShow['ShowName'])+'\n'
                local.output+='outYear='+str(parsedShow['Year'])+'\n'
                local.output+='outSeason='+str(parsedShow['Season'])+'\n'
                local.output+='outEpisode='+str(parsedShow['Episode'])+'\n'
                local.output+='outGroup='+str(parsedShow['Group'])+'\n'
                local.output+='outQuality='+str(parsedShow['Quality'])+'\n'
                local.output+='outSize='+str(parsedShow['Size'])+'\n'
                local.output+='outUndesired='+str(parsedShow['Undesired'])+'\n'
                local.output+='outUnknown='+str(parsedShow['Unknown'])+'\n'
                local.output+='\n'
            
            with lock:
                if not parsedShow['ShowName']:
                    statistics['Failed'] += 1
                    if Debug > -1:
                        local.output+='! Error, failed to parse show name from: '+originalFilename+'\n'
                    continue
                
                if len(parsedShow['Size'])>1:
                    statistics['Errors'] += 1
                    if Debug > -1:
                        local.output+='! Error, two Sizes in file: '+str(parsedShow['Size'])+' in '+originalFilename+'\n'
                
                if not parsedShow['Group']:
                    statistics['Errors'] += 1
                    if Debug > -1:
                        local.output+="! Error, couldn't parse Release Group from: "+originalFilename+'\n'

                if parsedShow['Season'] and parsedShow['Episode']:
                    statistics['Shows'] += 1
                else:
                    statistics['Movies'] += 1

            if Debug > 2:
                local.output+='------------------\n'
            
            if not loggedIn:
                if Debug > -1:
                    local.output+='Not logged in, skipping searching for new subtitles\n'
                continue
            
            subtitle = ltv.search(parsedShow)
            
            if not subtitle:
                with lock:
                    if local.wanted_languages == preferred_languages:
                        statistics['NoSubs'] += 1
                        if Debug > -1:
                            local.output+='No subtitles found\n'
                    else:
                        statistics['NoBest'] += 1
                        if Debug > -1:
                            local.output+='No better subtitles found\n'
                continue
            
            if subtitle['%'] < confidence_threshold:
                with lock:
                    if local.wanted_languages == preferred_languages:
                        statistics['NoSubs'] += 1
                    else:
                        statistics['NoBest'] += 1
                if Debug > -1:
                    local.output+='Only bad subtitles, similiarity: '+str(subtitle['%'])+'\n'
                continue
                
            if not ltv.download(subtitle):
                local.output+='. Failed to download subtitle, retrying in 3s\n'
                time.sleep(random.uniform(1.0, 4.0))
                if not ltv.download(subtitle):
                    if Debug > -1:
                        local.output+='. Failed to download subtitle: '+subtitle['release']+'\n'
                    continue
            
            if Debug == 0:
                local.output+='ed: '+subtitle['language']
                
            ltv.extract_sub(dirpath, originalFilename, parsedShow, subtitle['language'])
            if Debug == 0:
                local.output+=', '+subtitle['release']+'\n'
            continue


        except (Empty):
            #print('Waiting for jobs for '+str(threading.current_thread().getName()))
            if Done:
                return
            time.sleep(random.uniform(0.5, 1.0))
            pass
        except:
            print('print_exc():')
            traceback.print_exc(file=sys.stdout)
            return


## Main starts here
## Main starts here
## Main starts here
## Main starts here
## Main starts here
## Main starts here
## Main starts here
## Main starts here
## Main starts here
## Main starts here
## Main starts here
## Main starts here

if __name__ == '__main__':

    global statistics
    global ltv

    preferred_languages = [x.lower() for x in preferred_languages]
    clean_name_from = [x.lower() for x in clean_name_from]
    valid_video_extensions = [x.lower() for x in valid_video_extensions]
    valid_subtitle_extensions = [x.lower() for x in valid_subtitle_extensions]
    
    known_release_groups = [x.lower() for x in known_release_groups]
    garbage = [x.lower() for x in garbage]
    undesired = [x.lower() for x in undesired]
    video_quality = [x.lower() for x in video_quality]
    video_size = [x.lower() for x in video_size]
    
    sizeRegex = re.compile("("+'|'.join(video_size)+")(i|p)", re.I)
    
    statistics={'Videos':0, 'NotVideos':0, 'Folders':0, 'Shows':0, 'Movies':0, 'Failed':0, 'Errors':0, 'Best':0, 'DL':0, 'Upg':0, 'NoBest':0, 'NoSubs':0, 'PT':0, 'BR':0, 'EN':0}

    loggedIn = False
    ltv = LegendasTV(ltv_username, ltv_password)

    if not OnlyIMDBRating:
        if Debug > -1:
            print('Logging in Legendas.TV')
        if ltv.login():
            loggedIn = True
            if Debug > 0:
                print('Logged with success!')
        else:
            if Debug > -1:
                print('Failed to Log In. Is the website Up?')
            Done=True
            

    input_string = sys.argv[1:]

    if len(input_string) == 0:
        input_string.append(default_folder)

    # Mark where the original input ends
    input_string.append("-OI")

    videosQ = Queue()

    # Start worker threads here
    for i in range(thread_count):
        t = threading.Thread(target=ltvdownloader, args = (videosQ,) ) #, daemon=True)
        t.start()


    if Debug > -1:
        print('Parsing arguments. First results can take a few seconds.\n')

    OriginalInputFinished = False

    count=0
    # Parsing all arguments (Files)
    for originalFilename in input_string:
        dirpath=''
        
        if Done: # Signal received
            break

        if (sys.version_info < (3, 0)):
            originalFilename = originalFilename.decode(sys.getfilesystemencoding(), "ignore")

        # Flag to remove garbage from filename in this item
        clean_name = clean_original_filename

        if originalFilename == '-r':
            recursive_folders = True
            continue

        if originalFilename == '-OI':
            OriginalInputFinished = True
            continue

        if originalFilename == '-f':
            ForceSearch = True
            continue

        if originalFilename == '-OnlyIMDBRating':
            if Debug > -1:
                print('Only doing IMDB Rating!')
            OnlyIMDBRating = True
            continue

        if originalFilename == '-s': # silentMode
            getch = lambda:None
            continue

        if originalFilename == '-d':
            Debug = 2
            continue

        if originalFilename == '-dd':
            Debug = 4
            continue


        if os.path.islink(originalFilename):
            if Debug > 0:
                print('Symbolic link ignored! %s' % (os.path.basename(originalFilename)))
            statistics['NotVideos'] += 1
            continue
        
        if os.path.isfile(originalFilename):
            if originalFilename.endswith(tuple(valid_extension_modifiers)):
                originalFilename = os.path.splitext(originalFilename)[0]
                clean_name = False # Can't rename

            if not originalFilename.endswith(tuple(valid_video_extensions)):
                if Debug > 2:
                    print('Not a video file: %s' % (os.path.basename(originalFilename)))
                statistics['NotVideos'] += 1
                continue
            if len(input_string)<=2:
                ForceSearch=True
                if Debug > -1:
                    print('Single argument: Forcing search, ignore existing subs')
        
        elif os.path.isdir(originalFilename):
            if not recursive_folders:
                if fix_ETTV_subfolder and re.match(".+[^a-zA-Z0-9]S\d\dE\d\d(E\d\d)?[^a-zA-Z0-9].+", originalFilename):
                    if Debug > 0:
                        print('Found ETTV folder: %s' % (originalFilename))
                elif OriginalInputFinished:
                    if Debug > 2:
                        print('Directory found, recursiveness OFF: %s' % (originalFilename))
                    continue
                else:
                    if originalFilename != '.':
                        recursive_folders = True
                    if Debug > -1:
                        print('Searching whole directory: %s' % (originalFilename))
            else:
                if Debug > 0:
                    print('Recursing directory: %s' % (os.path.abspath(originalFilename)))

            if append_iMDBRating:
                originalFilename = getAppendRating((os.path.abspath(originalFilename)))

            statistics['Folders'] += 1
            for files in os.listdir(originalFilename):
                input_string.append(os.path.join(originalFilename, files))
            continue

        elif not os.path.exists(originalFilename):
            if Debug > 2:
                print('! Error, file not present! Moved? %s' % (originalFilename))
            continue

        else:
            statistics['Failed'] += 1
            if Debug > -1:
                print('! Error, Not a file nor a directory?!?! %s' % (originalFilename))
            continue
        
        statistics['Videos'] += 1

        if not os.path.dirname(os.path.abspath(originalFilename)):
            statistics['Failed'] += 1
            if Debug > -1:
                print('Error, no path!!')
            #dirpath = os.getcwd()
            continue

        if not OnlyIMDBRating:
            videosQ.put(os.path.abspath(originalFilename))

    while not videosQ.empty():
        time.sleep(2)

    videosQ.join()
    Done=True

    if Debug > 2:
        print('------------------')
    
    if loggedIn:
        ltv.logout()
    
    if Debug > -1:
        
        print('\n\nFinal statistics:', end="")
        print('Failed!! %d, Errors: %d' % (statistics['Failed'], statistics['Errors'] ))
        
        print('\nFolders analyzed: %d' % (statistics['Folders']))
        print('Movies: %d,  Shows: %d,  NotVideos: %d' % (statistics['Movies'], statistics['Shows'], statistics['NotVideos']))
       
        print('\nSubtitles downloaded: %d, of which %d were upgrades' % (statistics['DL'], statistics['Upg']))
        print('PT: %d,  BR: %d,  EN: %d' % (statistics['PT'], statistics['BR'], statistics['EN']))
        
        print('\nFinal subtitles status in parsed library:')
        print('Best: %d,  Upgradeable: %d,  No Subs: %d' % (statistics['Best'], statistics['NoBest'], statistics['NoSubs']))

    if Debug > -1:
        print('\nPress any key to exit...')
        junk = getch()
        
    sys.exit()
