#!/usr/bin/env python
# -*- coding: utf-8 -*-

#### User Configurations ####

## Fill yours - This is again REQUIRED by the LTV website.
ltv_username = 'USERNAME'
ltv_password = 'PASS'

# Folder to scan when no arguments are passed
default_folder = '.'

# Ordered, from: pt, br, en
preferred_languages = ['pt','br','en']
rename_subtitle = True
append_language = True
append_confidence = False
clean_old_language = True

# Stop if #-Lang is already present: 1-PT, 2-PT/BR, 3-EN/PT/BR etc
stopSearchWhenExistsLang = 1

# Keeps a subtitle with the same name of the video (hard)linking to the best available subtitle. Occupies no space
hardlink_without_lang_to_best_sub = True

# Set this to 80 or 90 if you just want to download the best languague and subtitle
confidence_threshold = 50 

# Recursivity also becomes active after a '-r' argument
recursive_folders = False

# Append or update IMDB rating at the end of movie folders
# Folders must have the movie name followed by the year inside parenthesis, otherwise they are ignored
# eg: "Milk (2008)" becomes: "Milk (2008) [7.7]"
append_iMDBRating = True

# Rename and clean videos and accompanying files from this garbage-tags 
clean_original_filename = True
clean_name_from = ['VTV','www.torentz.3xforum.ro','MyTV','rarbg']

# No need to change those, but feel free to add/remove some
valid_subtitle_extensions = ['srt','txt','aas','ssa','sub','smi']
valid_video_extensions = ['avi','mkv','mp4','wmv','mov','mpg','mpeg','3gp','flv']
valid_extension_modifiers = ['!ut','part']

Debug = 0

####### End of regular user configurations #######

known_release_groups = ['LOL','2HD','ASAP','FQM','Yify','killers','fum','fever','p0w4','FoV','TLA','refill','notv','reward','bia','maxspeed','FiHTV','BATV','SickBeard']

## Set this flag using -f as parameter, to force search and replace all subtitles. 
## This option is implied when only one argument is passed (single file dragged & dropped)
ForceSearch=False
OnlyIMDBRating = False

## LegendasTV timeout and number of threads to use. Increasing them too high may affect the website performance, please be careful
ltv_timeout = 15
thread_count = 5


####### Dragons ahead !! #######

Done = False


import os, sys, traceback
import json, re
import glob, filecmp, tempfile
import signal, platform
import threading, queue, time, random

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
    fd = sys.stdin.fileno()
    tty.setraw(sys.stdin.fileno())
    getch = sys.stdin.read(1)


REQUIREMENTS = [ 'requests' , 'beautifulsoup4', 'rarfile' ]

try:
    import requests
    from bs4 import BeautifulSoup
    from rarfile import RarFile
except:
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
    print('Installing requirements: ' + str(REQUIREMENTS))
    pip.main(pip_args)
    # pip.main(initial_args = pip_args)
 
    # do it again
    try:
        import requests
        from bs4 import BeautifulSoup
        from rarfile import RarFile
        print('Sucessfully installed the required libraries\n')
    except:
        print('\nPython modules needed: beautifulsoup4, rarfile, requests')
        print('We failled to install them automatically.')
        print('\nTry running this with Admin Priviliges, or')
        print('Run in a command prompt Admin Priviliges:\n')
        print('pip install requests beautifulsoup4 rarfile')
        print('\nPress any key to exit...')
        if Debug > -1:
            junk = getch()
        sys.exit()



def signal_handler(signal, frame):
    global videosQ, Done
    Done=True
    videosQ.queue.clear()
    print('Cleared List. Terminating in 5s')
    time.sleep(5)
    sys.exit()
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

def UpdateFile(file1, file2):
    exc = ""
    for x in [1, 2, 3]: 
        try:
            if not os.path.isfile(file1):
                return False
            
            if not os.path.isfile(file2):
                os.rename(file1, file2)
                return True
            
            if SameFile(file1, file2):
                os.remove(file1)
                return True
            
            if os.path.getsize(file1) < 1500 and os.path.getsize(file2) > 1500:
                os.remove(file1)
                return True
                
            if os.path.getsize(file2) < 1500 and os.path.getsize(file1) > 1500:
                os.remove(file2)
                os.rename(file1, file2)
                return True
                
            if os.path.getmtime(file1) < os.path.getmtime(file2):
                os.remove(file1)
                return True
                
            if os.path.getmtime(file2) < os.path.getmtime(file1):
                os.remove(file2)
                os.rename(file1, file2)
                return True
            
            if os.path.getsize(file1) < os.path.getsize(file2):
                os.remove(file1)
                return True
                
            if os.path.getsize(file2) < os.path.getsize(file1):
                os.remove(file2)
                os.rename(file1, file2)
                return True
            
            os.remove(file2)
            os.rename(file1, file2)
            return True
            
        except (Exception) as e:
            exc = e
            time.sleep(0.5)
            pass
    
    print('\nSomething went wrong renaming files: '+str(type(exc))+'\n'+file1+'\nto:\n'+file2)
    return False


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
        
        if "Usuário ou senha inválidos" in r.text:
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
    def search(self, videoTitle, videoSubTitle, year, season, episode, group, size, quality):
        
        if Debug > 2:
            local.output+='------- Searching -------\n'
        if Debug > 2:
            local.output+='Title: '+', '.join(videoTitle)+'\n\
        SubTitle: '+', '.join(videoSubTitle)+'\n\
        year: '+str(year)+'\n\
        season: '+str(season)+'\n\
        episode: '+str(episode)+'\n\
        wanted_languages: '+', '.join(local.wanted_languages)+'\n\
        group: '+group+'\n\
        size: '+size+'\n\
        quality: '+', '.join(quality)+'\n'
        
        list_possibilities = []

        for iTry in 1,2,3:
            if len(list_possibilities) > 0:
                break
            vsearch_array = []

            if season and episode:
                if iTry == 1:
                    vsearch_array.append(' '.join(videoTitle)+' '+season+'E'+episode)

                if iTry == 2:
                    vsearch_array.append(' '.join(videoTitle)+' '+season+'x'+episode)

                if iTry == 3:
                    vsearch_array.append(' '.join(videoTitle)+' '+season+episode)
                    ## vsearch_array.append(' '.join(videoTitle)+' '+season+' '+episode)
                
            else:
                if iTry == 1:
                    
                    if videoSubTitle and group and year:
                        vsearch_array.append(' '.join(videoTitle+videoSubTitle+[str(group)]+[str(year)]))
                    
                    if videoSubTitle and year:
                        vsearch_array.append(' '.join(videoTitle+videoSubTitle+[str(year)]))
                    
                    if videoSubTitle:
                        vsearch_array.append(' '.join(videoTitle+videoSubTitle))
                    
                    if year:
                        vsearch_array.append(' '.join(videoTitle+[str(year)]))
                    
                if iTry == 2:
                    if videoSubTitle and group:
                        vsearch_array.append(' '.join(videoTitle+videoSubTitle+[str(group)]))
                    
                    if group and year:
                        vsearch_array.append(' '.join(videoTitle+[str(group)]+[str(year)]))
                    
                if iTry == 3:
                    if group:
                        vsearch_array.append(' '.join(videoTitle+[str(group)]))
                    
                    vsearch_array.append(' '.join(videoTitle))

            ## Search 6 pages and build a list of possibilities
            for vsearch in vsearch_array:
                
                
                # vsearch = urllib.parse.quote(vsearch)
                for vsearch_prefix in ['/-/-', '/-/-/2', '/-/-/3', '/-/-/4', '/-/-/5', '/-/-/6']:
                    newPossibilities = 0
                    
                    if Debug < 2:
                        local.output+='. '
                    else:
                        local.output+="Searching for subtitles with: "+vsearch+" , "+vsearch_prefix+'\n'
                    
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
                        
                    soup = BeautifulSoup(r.text)

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
                                sub = span.find('a').contents[0]

                                flag = span.find('img').get('src')
                            except:
                                if Debug > 2:
                                    local.output+="! Error parsing result list: "+span.prettify()+'\n'
                                continue

                            if not td:
                                if Debug > 2:
                                    local.output+='#### Something went wrong ####\n'
                                continue

                            possibility = {}
                            possibility.clear()
                            
                            newPossibilities += 1

                            # Parse the link
                            tmpregex = re.search('/download/(\w+)/(\w+)/(\w+)',td)

                            if not tmpregex or tmpregex.lastindex<3:
                                local.output+='#### Error parsing link:'+td+' ####\n'
                                continue

                            # Get the download ID
                            download_id = tmpregex.group(1)
                            release = tmpregex.group(3)

                            if download_id in [x['id'] for x in list_possibilities]:
                                continue

                            possibility['id'] = download_id
                            if not download_id:
                                if Debug > 2:
                                    local.output+='Couldn\'t get download_id\n'
                                continue
                            
                            possibility['release'] = release.lower()
                            if not possibility['release']:
                                if Debug > 2:
                                    local.output+='Couldn\'t get Release\n'
                                continue
                            
                            ## Get the language
                            tmpregex = re.search('/\w*/(?:icon|flag)_(\w+)\.(gif|jpg|jpeg|png)',flag)
                            
                            if not tmpregex or tmpregex.lastindex<2:
                                local.output+='#### Error parsing flag: '+flag+' ####\n'
                                continue
                            language = tmpregex.group(1)

                            if 'pt' in language:
                                possibility['language'] = 'pt'
                            elif 'braz' in language:
                                possibility['language'] = 'br'
                            elif 'usa' in language:
                                possibility['language'] = 'en'


                            if not 'language' in possibility or not possibility['language']:
                                if Debug > 2:
                                    local.output+='Couldn\'t get Language\n'
                                continue
                            
                            ## Now it doesn't have a SubName
                            possibility['sub_name'] = sub.lower()
                            
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
                            
                            possibility['%'] = 100
                            
                            list_possibilities.append(possibility)
                            if Debug > 2:
                                local.output+='FOUND!: '+possibility['language']+' - '+possibility['release']+'\n'


                    if Debug > 2:
                        local.output+='Got results: '+str(newPossibilities)+'\n'

                    if newPossibilities < 20:
                        break

        if len(list_possibilities) == 0:
            if Debug > 2:
                local.output+='No subtitles found\n'
            with lock:
                statistics['NoSubs'] += 1
            return False
            
        # Calculate similarity for every possibility
        for possibility in list_possibilities:
            if Debug > 2:
                local.output+='--------\n'
            if Debug > 2:
                local.output+='Analyzing '+possibility['release']+'\n'

            # Filter wanted_languages
            possibility['language'] = possibility['language'].replace('us', 'en')
            if possibility['language'] not in preferred_languages:
                if Debug > 2:
                    local.output+='0!!, Wrong language: '+possibility['language']+', from: '+str(preferred_languages)+'\n'
                possibility['%'] = 0
                continue
            
            for index, tmp in enumerate(preferred_languages):
                if tmp == possibility['language']:
                    if Debug > 2:
                        local.output+='-'+str(index*21)+', Language '+possibility['language']+' at pos '+str(index)+'\n'
                    possibility['%'] -= 21*index
                    break
            
            # Evaluate name
            for tmp in [j for j in videoTitle]:
                if tmp.lower() not in possibility['sub_name'] and tmp.lower() not in possibility['release']:
                    if Debug > 2:
                        local.output+='-15, Missing word: '+tmp+' in name: '+possibility['sub_name']+'\n'
                    possibility['%'] -= 15*index
        
            # Evaluate season number in name
            if season:
                if season not in possibility['sub_name'] and season not in possibility['release']:
                    if Debug > 2:
                        local.output+='-15, Missing Season: '+season+' in name: '+possibility['sub_name']+'\n'
                    possibility['%'] -= 15*index

            # Filter group
            if group not in possibility['release']:
                if Debug > 2:
                    local.output+='-20, Correct group not found: '+group+'\n'
                possibility['%'] -= 20
            
            # Filter size
            if size:
                if size not in possibility['release']:
                    if Debug > 2:
                        local.output+='-14, Correct size not found: '+size+'\n'
                    possibility['%'] -= 14
            
            # Evaluate quality
            for tmp in quality:
                denormalizedQuality = deNormalizeQuality(tmp)
                for tmp2 in denormalizedQuality:
                    if tmp2 in possibility['release']:
                        break
                    if tmp2 == denormalizedQuality[-1]:
                        if Debug > 2:
                            local.output+='-5, Correct quality not found: '+tmp2+'\n'
                        possibility['%'] -= 5

            # Devalue undesired words
            for tmp in undesired:
                if tmp in possibility['release']:
                    if Debug > 2:
                        local.output+='-2, Undesired found: '+tmp+'\n'
                    possibility['%'] -= 2

        if Debug > 2:
            local.output+='------------------\n'
        final_list = sorted(list_possibilities, key=lambda k: k['%'], reverse=True)
        
        for idx, possibility in enumerate(final_list):
            if Debug > 1:
                local.output+='Chance '+str(idx)+', '+str(possibility['%'])+'%, '+possibility['language']+', '+possibility['release']+'\n'
        
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
                local.output+='------- Downloading -------\n'
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
    def extract_sub(self, dirpath, originalFilename, group, size, quality, language):
        global lock
        if Debug > 2:
            local.output+='------- Extracting -------\n'
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
                if Debug > -1:
                    local.output+='! Error, Error opening archive: '+self.archivename+'\n'
                    local.output+='UNRAR must be available on console\n'
                return False

        language_compensation = -1
        for index, tmp in enumerate(local.wanted_languages):
            if tmp == language:
                language_compensation = 15*index
                break
        if language_compensation == -1:
            local.output+='No language? '+language+'\n'
            language_compensation = 0

        files = archive.infolist()
            
        srts = []
        current_maxpoints = 0
        current_maxfile = []

        unique_compensation = 0
        if len(files) == 1:
            unique_compensation = 15

        for srtname in files:
            points = 100 - language_compensation + unique_compensation

            testname = srtname.filename.lower()
            if not testname.endswith(tuple(valid_subtitle_extensions)+('rar', 'zip')):
                if Debug > 2:
                    local.output+='Non Sub file: ' + str(srtname)+'\n'
                continue

            if Debug > 2:
                local.output+='Analyzing: '+str(testname)+'\n'

            # if language not in testname:
            #     if Debug > 2:
            #         local.output+='-1, Language not in FileName: '+language+'\n'
            #     points-=1
                
            if group not in testname:
                if Debug > 2:
                    local.output+='-30, Correct Release not found: '+group+'\n'
                points-=30
                
            for tmp in quality:
                denormalizedQuality = deNormalizeQuality(tmp)
                for tmp2 in denormalizedQuality:
                    if tmp2 in testname:
                        break
                    if tmp2 == denormalizedQuality[-1]:
                        if Debug > 2:
                            local.output+='-5, Correct quality not found: '+tmp2+'\n'
                        points-=5

            for tmp in undesired:
                if tmp in testname:
                    if Debug > 2:
                        local.output+='-5, Undesired word found: '+tmp+'\n'
                    points-=5
            if size:
                if size not in testname:
                    if Debug > 2:
                        local.output+='-15, Correct size not found: '+size+'\n'
                    points-=15
            else:
                if re.search("("+'|'.join(video_size)+")(i|p)?", testname, re.I):
                    if Debug > 2:
                        local.output+='-20, Too much size found: ' + srtname.filename+'\n'
                    points-=20
            if Debug > 2:
                local.output+='Adding subtitle file with points '+str(points)+': '+srtname.filename+'\n'

            if current_maxpoints<points:
                current_maxpoints = points
                current_maxfile = srtname

        if Debug > 2:
            local.output+='-------\n'

        if points<1 or not current_maxfile:
            if Debug > -1:
                local.output+='! Error: No valid subs found on archive\n'
            with lock:
                statistics['Failed'] += 1
            return False

        extract = []
        
        #if Debug > 2:
        #    local.output+='Ext '+str(idx)+', '+str(p)+'%: '+os.path.basename(n.filename)+'\n'

        #if srts[0][0] > confidence_threshold:
        #    extract.append(srts[0][1])
        extract.append(current_maxfile)

        # maximum=confidence_threshold
        # for idx, [p, n] in enumerate(srts):
        #     print "Result %d, %d%%: %s" % (idx, p, n.filename)
        #     if p >= maximum:
        #         maximum = p
        #         extract.append(n)
            
        ## Extracting
        for fileinfo in extract:
            fileinfo.filename = os.path.basename(fileinfo.filename)
            
            if Debug > 2:
                local.output+='Extracting file: '+fileinfo.filename+'\n'

            if fileinfo.filename.endswith(('rar', 'zip')):
                if Debug > 2:
                    local.output+='Recursive extract, RAR was inside: '+fileinfo.filename+'\n'
                archive.extract(fileinfo, self.download_path)
                self.archivename = os.path.join(self.download_path, fileinfo.filename)
                if not ltv.extract_sub(dirpath, originalFilename, group, size, quality, language):
                    return False
                continue
                
            dest_filename = fileinfo.filename

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
            
            except (Exception):
                with lock:
                    statistics['Failed'] += 1
                if Debug > -1:
                    local.output+='! Error, decrompressing!\n'
                return False

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
        
# Remove garbage from filenames
def cleanAndRenameFile(Folder, filename):

    # Generate Regex
    regex = '(' + '|'.join(clean_name_from)+')'

    if not re.search('\W'+regex+'\W', filename, re.I):
        return filename

    fullFilename = os.path.join(Folder, filename)
    statementClean = re.compile('\W?[\[\(\{]?'+regex+'[\]\)\}]?', re.I)
    newname = statementClean.sub('', filename)

    fullNewname = os.path.join(Folder, newname)

    # Sanity check
    if newname == filename:
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

    
    # Cleaning subtitles and other files
    glob_pattern = re.sub(r'(?<!\[)\]', '[]]', re.sub(r'\[', '[[]', os.path.splitext(fullFilename)[0]+'.*'))
    for tmpFile in glob.glob(glob_pattern):
        tmpNew = statementClean.sub('', tmpFile)
        if tmpNew == tmpFile:
            if Debug > 2:
                local.output+='Error cleaning this name: '+tmpFile+'\n'
        else:
            if Debug > 2:
                local.output+='Found and removing '+regex+' in '+tmpFile+'\n'
            
            if UpdateFile(tmpFile, tmpNew):
                if Debug > -1:
                    local.output+='Renamed sub to: '+tmpNew+'\n'
            else:
                if Debug > -1:
                    local.output+='! Error renaming subtitles: '+tmpFile+'\n'
        
    return newname

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

# Normalize usual video tags for easier comparison
def normalizeTags(tag):
    tag = tag.lower()
    if tag in ['bluray', 'blueray', 'brip', 'brrip', 'bdrip']:
        return 'bluray'
    if tag in ['dvdrip', 'dvd', 'sd']:
        return 'dvd'
    if tag in ['x264', 'h264']:
        return 'x264'

    if tag in ['480', '480p', '480i']:
        return '480'
    if tag in ['540', '540p', '540i']:
        return '540'
    if tag in ['720', '720p', '720i']:
        return '720'
    if tag in ['1080', '1080p', '1080i']:
        return '1080'

    if tag in ['directors', 'dircut']:
        return 'directors'
    return tag

def deNormalizeQuality(quality):
    quality = quality.lower()
    if quality in ['bluray', 'blueray', 'brip', 'brrip', 'bdrip']:
        return ['bluray', 'blueray', 'brip', 'brrip', 'bdrip']
    if quality in ['dvdrip', 'dvd', 'sd']:
        return ['dvdrip', 'dvd', 'sd']
    if quality in ['x264', 'h264']:
        return ['x264', 'h264']
    return [quality]


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
        
    elif search:
        payload['s'] = movie
        if withYear:
            payload['y'] = year
    else:
        payload['t'] = movie
        if withYear:
            payload['y'] = year
            
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
    if Debug > 0:
        print('Got imdb: '+str(data))
        
    if search:
        if 'Search' in data.keys():
            data["Search"] = [item for item in data["Search"] if item["Type"]=="movie"]
            
            if len(data["Search"])==1 and 'imdbID' in data["Search"][0].keys():
                if Debug > 0:
                    print("Found the movie: " + data["Search"][0]["Title"])
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
        print("Year changed for: " + movie + ", " + year + " to " + data["Year"])
        year = data["Year"]
        changed = True

    if 'imdbRating' in data.keys() and rating != data["imdbRating"] and not '/' in data["imdbRating"]:
        print("Rating changed for: " + movie + ", " + rating + " to " + data["imdbRating"])
        rating = data["imdbRating"]
        changed = True

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
        print("Rating didn't change for: " + foldername)
    return fullFilename


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

            # Start analyzis per-se
            search_string = originalFilename.lower()
            search_string = re.split('[\ \.\-\_\[\]\&\(\)]', search_string)

            # Removing empty strings
            search_string = [ st for st in search_string if st ]

            # Removing Extensions
            if search_string[-1] in valid_extension_modifiers:
                search_string.pop()
            if search_string[-1] in valid_video_extensions:
                search_string.pop()
            if search_string[-1] in valid_video_extensions:
                search_string.pop()

            # Clean first word if number
            if re.match("^\d\d$", search_string[0]):
                search_string.pop(0)

            # Removing Garbage
            for idx, val in reversed(list(enumerate(search_string))):
                if val in garbage:
                    search_string.pop(idx)
                    continue
            
            if len(search_string)==0:
                if Debug > -1:
                    local.output+='! Error, this video is just garbage: '+originalFilename+'\n'
                with lock:
                    statistics['Failed'] += 1
                continue


            sizeRegex = re.compile("("+'|'.join(video_size)+")(i|p)?", re.I)

            possibleGroup = search_string[0]
            tagFound=0
            for item in search_string:
                
                # found season and episode tag
                if re.match("[s]?\d?\d[xe]\d\d([xe]\d\d)?$", item, re.I):
                    season=re.sub("[s]?0?([1-9]?\d)[xe](\d\d)([xe](\d\d))?", '\\1', item)
                    episode=re.sub("[s]?0?([1-9]?\d)[xe](\d\d)([xe](\d\d))?", '\\2', item)
                    tagFound = 1
                    continue

                # 2CDs video found
                if re.match("^cd\d$", item, re.I):
                    quality.append('2cd')
                    quality.append(item)
                    tagFound = 1
                    continue

                # found well-known group
                if item in release_groups:
                    group = item
                    tagFound = 1
                    continue

                # found generic quality tag
                if item in video_quality:
                    quality.append(item)
                    tagFound = 1
                    continue

                # found video resolution tag
                if sizeRegex.match(item):
                    if size:
                        with lock:
                            statistics['Errors'] += 1
                        if Debug > 2:
                            local.output+='! Error, 2 Sizes in file?!?! '+size+' & '+item+'\n'
                    size = sizeRegex.sub('\\1', item)
                    tagFound = 1
                    continue
                
                # Removing Year
                if re.match("\d{4}", item):
                    year = item
                    tagFound = 1
                    continue

                if not tagFound:
                    videoTitle.append(item)
                    if re.match("^\d$", item):
                        tagFound = 2
                    # After a number, consider the rest as subtitle
                elif tagFound == 2:
                    videoSubTitle.append(item)
                else:
                    # Last unknown is usually the release group
                    possibleGroup = item

                continue
            
            ########################
            
            if not videoTitle:
                with lock:
                    statistics['Failed'] += 1
                if Debug > -1:
                    local.output+='! Error, no name detected\n'
                continue

            if not group:
                group = possibleGroup
                if Debug > 0:
                    local.output+='Group not known. Using: '+group+'\n'

            with lock:
                if season and episode:
                    statistics['Shows'] += 1
                else:
                    statistics['Movies'] += 1

            if Debug > 2:
                local.output+='------------------\n'

            subtitle = ltv.search(videoTitle, videoSubTitle, year, season, episode, group, size, quality)
            if subtitle and subtitle['%'] < confidence_threshold:
                with lock:
                    if local.wanted_languages == preferred_languages:
                        statistics['NoSubs'] += 1
                    else:
                        statistics['NoBest'] += 1

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
                if Debug > -1:
                    local.output+='Only bad subtitles, similiarity: '+str(subtitle['%'])+'\n'
                continue
                
            if not ltv.download(subtitle):
                time.sleep(random.uniform(1.0, 4.0))
                if not ltv.download(subtitle):
                    if Debug > -1:
                        local.output+='. Failed to download subtitle: '+subtitle['release']+'\n'
                    continue
            
            if Debug == 0:
                local.output+='ed: '+subtitle['language']
            ltv.extract_sub(dirpath, originalFilename, group, size, quality, subtitle['language'])
            if Debug == 0:
                local.output+=', '+subtitle['release']+'\n'
            continue


        except (queue.Empty):
            #print('Waiting for jobs for '+str(threading.current_thread().getName()))
            if Done:
                return
            time.sleep(random.uniform(1.0, 4.0))
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

    garbage = [x.lower() for x in ['Unrated', 'DC', 'Dual', 'VTV', 'eng', 'subbed', 'artsubs', 'sample', 'ExtraTorrentRG', 'StyLish', 'Release', 'US' ]]
    undesired = [x.lower() for x in ['.HI.', '.Impaired.', '.Comentários.', '.Comentarios.' ]]
    video_quality = [x.lower() for x in ['HDTV', 'XviD', 'DivX', 'x264', 'BluRay', 'BRip', 'BRRip', 'BDRip', 'DVDrip', 'DVD', 'AC3', 'DTS', 'TS', 'R5', 'R6', 'DVDScr', 'PROPER', 'REPACK' ]]
    video_size = [x.lower() for x in ['480', '720', '1080']]
    release_groups = [x.lower() for x in known_release_groups]

    preferred_languages = [x.lower() for x in preferred_languages]
    clean_name_from = [x.lower() for x in clean_name_from]
    valid_video_extensions = [x.lower() for x in valid_video_extensions]
    valid_subtitle_extensions = [x.lower() for x in valid_subtitle_extensions]
    
    statistics={'Videos':0, 'NotVideos':0, 'Folders':0, 'Shows':0, 'Movies':0, 'Failed':0, 'Errors':0, 'Best':0, 'DL':0, 'Upg':0, 'NoBest':0, 'NoSubs':0, 'PT':0, 'BR':0, 'EN':0}


    ltv = LegendasTV(ltv_username, ltv_password)

    if Debug > -1:
        print('Logging in Legendas.TV')
    
    if not ltv.login():
        if Debug > -1:
            print('Press any key to exit...')
        junk = getch()
        sys.exit()
    
    if Debug > 0:
        print('Logged with success!')

    input_string = sys.argv[1:]

    if len(input_string) == 0:
        input_string.append(default_folder)

    # Mark where the original input ends
    input_string.append("-OI")

    videosQ = queue.Queue()

    # Start worker threads here
    for i in range(thread_count):
        t = threading.Thread(target=ltvdownloader, args = (videosQ,), daemon=True)
        t.start()


    if Debug > -1:
        print('Listing files. First results can take a few seconds.\n')

    OriginalInputFinished = False

    count=0
    # Parsing all arguments (Files)
    for originalFilename in input_string:
        dirpath=''

        if Done: # Signal received
            break

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
            OnlyIMDBRating = True
            continue

        if originalFilename == '-s':
            silentMode = True
            getch = None
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
                    local.output+='Single argument: Forcing search, ignore existing subs\n'
        
        elif os.path.isdir(originalFilename):

            if not recursive_folders:
                if OriginalInputFinished:
                    if Debug > 2:
                        print('Directory found, recursiveness OFF: %s' % (originalFilename))
                    continue
                else:
                    if originalFilename != '.':
                        recursive_folders = True
                    if Debug > -1:
                        print('Searching whole directory: %s' % (os.path.abspath(originalFilename)))
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
        time.sleep(1)

    videosQ.join()
    Done=True

    if Debug > 2:
        print('------------------')
    
    
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
