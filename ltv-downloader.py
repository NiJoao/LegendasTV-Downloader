#!/usr/bin/env python
# -*- coding: utf-8 -*-

#### User Configurations ####

## Fill yours - This is OPTIONAL for now! The site doesn't require login anymore
ltv_username = ''
ltv_password = ''

# Folder to scan when no arguments are passed
default_folder = '.'

# Ordered, from: pt, br, en
preferred_languages = ['pt','br','en']
rename_subtitle = True
append_language = True
clean_old_language = True

# Keeps a subtitle with the same name of the video (hard)linking to the best available subtitle. Occupies no space
hardlink_without_lang_to_best_sub = True

# Set this to 80 or 90 if you just want to download the best languague and subtitle
confidence_threshold = 50 

# Recursivity also becomes active after a '-r' argument
recursive_folders = False

# Rename and clean videos and accompanying files from this garbage-tags 
clean_original_filename = True
clean_name_from = ['VTV','www.torentz.3xforum.ro','MyTV']

# No need to change those, but feel free to add/remove some
valid_subtitle_extensions = ['srt','aas','ssa','sub','smi']
valid_video_extensions = ['avi','mkv','mp4','wmv','mov','mpg','mpeg','3gp','flv']
valid_extension_modifiers = ['!ut','part']

known_release_groups = ['LOL','2HD','ASAP','FQM','Yify','fever','p0w4','FoV','TLA','refill','notv','reward','bia','maxspeed']

Debug = 0

####### End of user configurations #######

####### Dragons ahead !! #######

import http.cookiejar, urllib.request, urllib.error, urllib.parse, urllib.request, urllib.parse, urllib.error
import re, os, sys, filecmp, tempfile, traceback, shutil, getpass, time, random
import glob

from zipfile import ZipFile
from urllib.error import HTTPError, URLError
from operator import itemgetter

import  threading, queue
lock = threading.Lock()
local = threading.local()
local.output = ''
local.wanted_languages = []

## Set this flag using -f as parameter
ForceSearch=False

Done=False
thread_count = 5

import signal
def signal_handler(signal, frame):
    global videosQ, Done
    Done=True
    videosQ.queue.clear()
    print('Cleared List. Terminating in 5s')
    time.sleep(5)
    sys.exit()
signal.signal(signal.SIGINT, signal_handler)

import platform

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

try:
    from bs4 import BeautifulSoup
except ImportError:
    print('Python module needed: BeautifulSoup4 / bs4')
    print('\nPress any key to exit...')
    junk = getch()
    sys.exit()
    
try:
    from rarfile import RarFile
except ImportError:
    print('Python module needed: rarfile')
    print('\nPress any key to exit...')
    junk = getch()
    sys.exit()



def SameFile(file1, file2):
    try:
        return filecmp.cmp(file1, file2)
        # return os.stat(file1) == os.stat(file2)
    except:
        return False
os.path.samefile = SameFile

## Takes car of everything related to the Website
class LegendasTV:
    
    def __init__(self, ltv_username, ltv_password, download_dir=None):
        if not download_dir:
            download_dir = tempfile.gettempdir()

        self.download_path = os.path.abspath(download_dir)
        self.base_url = 'http://legendas.tv'
        self.username = ltv_username
        self.password = ltv_password

        self.cookieJar = http.cookiejar.CookieJar()
        self.opener= urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookieJar))
        urllib.request.install_opener(self.opener)

    ## Login in legendas.tv
    def login(self):
        name="data[User][username]"
        '''LoginForm:
            data[User][username] -> max_length(15)
            data[User][password] -> max_length(15)
            chkLogin -> 0|1 (keep logged?)
            _method -> POST
        '''
        login_data = urllib.parse.urlencode({'data[User][username]':self.username, 'data[User][password]':self.password, '_method':'POST'})
        request = urllib.request.Request(self.base_url+'/login',login_data)
        try:
            response = urllib.request.urlopen(request, timeout=10).read()
        except:
            if Debug > 0:
                print('login timedout, retrying')
            try:
                response = urllib.request.urlopen(request, timeout=10).read()
            except Exception:
                if Debug > -1:
                    print('! Error, login timeout?')
                    print('print_exc():')
                    traceback.print_exc(file=sys.stdout)
                return False

        if 'Dados incorretos' in response:
            if Debug > -1:
                print('! Error, wrong username or password ...')
            return False

        return True

    ## Logout
    def logout(self):
        request = urllib.request.Request(self.base_url+'/users/logout')
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except:
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

        for iTry in 1,2:
            if len(list_possibilities) > 0:
                break
            searchstr = []

            if season and episode:
                selType = 1

                if iTry == 1:
                    searchstr.append(' '.join(videoTitle)+' '+season+'E'+episode)
                    searchstr.append(' '.join(videoTitle)+' '+season+'x'+episode)

                if iTry == 2:
                    searchstr.append(' '.join(videoTitle)+' '+season+episode)

                if iTry > 2:
                    break
            else:
                if iTry == 1:
                    selType = 2
                    if videoSubTitle:
                        searchstr.append(' '.join(videoTitle+videoSubTitle+[str(year)]))

                    if year:
                        searchstr.append(' '.join(videoTitle+[str(year)]))
                if iTry == 2:
                    if not year:
                        continue
                    searchstr.append(' '.join(videoTitle))

                if iTry == 2:
                    selType = 1
                    if group:
                        if videoSubTitle:
                            if year:
                                searchstr.append(' '.join(videoTitle+videoSubTitle+[str(group)]+[str(year)]))
                            searchstr.append(' '.join(videoTitle+videoSubTitle+[str(group)]))

                        if year:
                            searchstr.append(' '.join(videoTitle+[str(group)]+[str(year)]))

                        searchstr.append(' '.join(videoTitle+[str(group)]))

                    if videoSubTitle:
                        if year:
                            searchstr.append(' '.join(videoTitle+videoSubTitle+[str(year)]))
                        searchstr.append(' '.join(videoTitle+videoSubTitle))
                    if year:
                        searchstr.append(' '.join(videoTitle+[str(year)]))
                    searchstr.append(' '.join(videoTitle))

            ## Search 6 pages and build a list of possibilities
            for vsearch in searchstr:
                for ltvpage in ['', '/page:2', '/page:3', '/page:4', '/page:5', '/page:6']:
                    newPossibilities = 0
                    
                    # search_dict = {'q':vsearch,'selTipo':selType,'int_idioma':LegendasTV.SearchLang.ALL}
                    # search_dict = {'q':vsearch,'selTipo':selType,'int_idioma':LegendasTV.SearchLang.ALL}
                    # search_data = urllib.urlencode(search_dict)
                    vsearch = urllib.parse.quote(vsearch)
                    
                    if Debug < 1:
                        local.output+='. '
                    else:
                        local.output+="Searching for subtitles with: "+vsearch+", Type "+str(selType)+" "+ltvpage+'\n'
                    
                    request = urllib.request.Request(self.base_url+'/util/carrega_legendas_busca/termo:'+vsearch+ltvpage)
                    try:
                        response = urllib.request.urlopen(request, timeout=15)
                        page = response.read()
                    except:
                        if Debug > 2:
                            local.output+='Search timedout, retrying\n'
                        try:
                            response = urllib.request.urlopen(request, timeout=15)
                            page = response.read()
                        except:
                            if Debug > 2:
                                local.output+='! Error, searching timedout\n'
                            return False
                    
                    soup = BeautifulSoup(page)

                    div_results = soup.find('div',{'class':'gallery clearfix list_element'}).findAll('article',recursive=False)
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
                            tmpregex = re.search('/img/\w*/(?:icon|flag)_(\w+)\.(gif|jpg|jpeg|png)',flag)
                            
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
            if Debug > 2:
                local.output+='Chance '+str(idx)+', '+str(possibility['%'])+'%%, '+possibility['language']+', '+possibility['release']+'\n'
        
        if final_list[0]['language'] not in local.wanted_languages:
            if Debug > 2:
                local.output+='\n-- Best subtitle already present --\n\n'
            return False
        
        return final_list[0]

    ## Downloads a subtitle given it's ID
    def download(self, subtitle):
        download_id = subtitle['id']
        if download_id:
            url_request = self.base_url+'/downloadarquivo/'+download_id
            if Debug == 0:
                local.output+='Download'
            if Debug > 2:
                local.output+='------- Downloading -------\n'
                local.output+='Downloading '+subtitle['language']+', '+subtitle['release']+'\n'
            request =  urllib.request.Request(url_request)
            try:
                response = urllib.request.urlopen(request, timeout=20)
                legenda = response.read()
            except:
                if Debug > 2:
                    local.output+="Download timedout, retrying\n"
                try:
                    response = urllib.request.urlopen(request, timeout=20)
                    legenda = response.read()
                except:
                    if Debug > 2:
                        local.output+="! Error, download timedout\n"
                    return False
            
            if 'Content-Disposition' in response.info():
                # If the response has Content-Disposition, we take file name from it
                localName = response.info()['Content-Disposition'].split('filename=')[1]
                if localName[0] == '"' or localName[0] == "'":
                    localName = localName[1:-1]

            if len(localName)>4:
                self.archivename= os.path.join(self.download_path, str(localName))
            else:
                self.archivename = os.path.join(self.download_path, str(download_id))

            if 'Content-Type' in response.info():
                if 'rar' in response.info().get('Content-Type'):
                    self.archivename += '.rar'
                elif 'zip' in response.info().get('Content-Type'):
                    self.archivename += '.zip'
                else:
                    if Debug > 2:
                        local.output+='No download MIME TYPE. Not forcing extension\n'

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
                with lock:
                    statistics['Failed'] += 1
                return False

        language_compensation = -1
        for index, tmp in enumerate(local.wanted_languages):
            if tmp == language:
                language_compensation = 15*index
                break
        if language_compensation == -1:
            local.output+='No language? '+language+'\n'

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
                #if Debug > 2:
                #    print 'Non Sub file: ' + str(srtname)
                continue

            if Debug > 2:
                local.output+='Analyzing: '+str(testname)+'\n'

            if language not in testname:
                if Debug > 2:
                    local.output+='-1, Language not in FileName: '+language+'\n'
                points-=1
                
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

        if points<1:
            if Debug > -1:
                local.output+='! Error: No valid subs found on archive\n'
            with lock:
                statistics['Failed'] += 1
            return False

        #sorted(srts, key=itemgetter(0), reverse=True)
        #srts.sort(reverse=True)
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
            
            if Debug > 2:
                local.output+='Extracting subtitle as: '+dest_filename+'\n'
            dest_fullFilename = os.path.join(dirpath, dest_filename)
            
            try:
                # fileinfo.filename = dest_filename
                # archive.extract(fileinfo, dirpath)

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
            
            except Exception:
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
    try:
        os.rename(fullFilename, fullNewname)
    except Exception:
        pass

    if not os.path.isfile(fullNewname):
        if Debug > 2:
            local.output+='! Error renaming. File in use? '+filename+'\n'
        return filename
    else:
        if Debug > -1:
            local.output+='Renamed to: '+newname+'\n'

    
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
            try:
                os.rename(tmpFile, tmpNew)
            except Exception:
                pass

            if not os.path.isfile(tmpNew):
                if Debug > -1:
                    local.output+='! Error renaming subtitles: '+tmpFile+'\n'
            else:
                if Debug > -1:
                    local.output+='Renamed sub to: '+tmpNew+'\n'
        
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
    except Exception:
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
    except Exception:
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
    if tag in ['dvdrip', 'dvd']:
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
    if quality in ['dvdrip', 'dvd']:
        return ['dvdrip', 'dvd']
    if quality in ['x264', 'h264']:
        return ['x264', 'h264']
    return [quality]

# Searchs for common 2-words tags and merges them into one
def mergeTags(search_string):
    out_array = []
    jump = False
    for idx, tag in list(enumerate(search_string)):
        if jump:
            jump = False
            continue
        
        if Debug > 2:
            local.output+='Analyzing '+tag+'\n'
            
        tag = normalizeTags(tag)
        
        # Always keep last one, no merging possible
        if idx == len(search_string) -1:
            out_array.append(tag)
            break

        if tag in ['directors'] and search_string[idx+1] == 'cut':
            out_array.append('directors')
            jump = True
            continue

        if tag in ['unrated', 'extended', 'special', 'directors' ] and search_string[idx+1] == 'edition':
            out_array.append(tag)
            jump = True
            continue
            
        out_array.append(tag)

    if Debug > 2:
        local.output+='done\n'
        local.output+=str(out_array)+'\n'
        

def parseFileName(filename):
    global lock
    garbage = [x.lower() for x in ['Unrated', 'DC', 'Dual', 'VTV', 'eng', 'subbed', 'artsubs', 'sample', 'ExtraTorrentRG', 'StyLish', 'Release' ]]
    video_quality = [x.lower() for x in ['HDTV', 'XviD', 'DivX', 'x264', 'BluRay', 'BRip', 'BRRip', 'BDRip', 'DVDrip', 'DVD', 'AC3', 'DTS', 'TS', 'R5', 'R6', 'DVDScr', 'PROPER', 'REPACK' ]]
    video_size = [x.lower() for x in ['480', '720', '1080']]
    release_groups = [x.lower() for x in known_release_groups]
    video_extras = [x.lower() for x in ['unrated', 'extended', 'special', 'directors' ]]
    
    data = {}
    data.clear()
    data['videoTitle'] = []
    data['videoSubTitle'] = []
    data['year'] = []
    data['season'] = []
    data['episode'] = []
    data['group'] = []
    data['quality'] = []
    data['size'] = []
    data['extras'] = []
    data['unknown'] = []

    search_string = filename.lower()
    search_string = re.split('[\ \.\-\_\[\]\&\(\)]', search_string)

    # Removing empty strings
    search_string = [ st for st in search_string if st ]

    normalizeTags(search_string)

    # Removing Extensions
    if search_string[-1] in valid_extension_modifiers:
        search_string.pop()
    if search_string[-1] in valid_video_extensions:
        search_string.pop()
    if search_string[-1] in valid_video_extensions:
        search_string.pop()

    # Clean first word if number
    #if re.match("^\d\d$", search_string[0]):
    #    search_string.pop(0)

    # Removing Garbage
    for idx, val in reversed(list(enumerate(search_string))):
        if val in garbage:
            search_string.pop(idx)
            continue
    
    if len(search_string)==0:
        if Debug > -1:
            local.output+='! Error, this filename is just garbage: '+filename+'\n'
        with lock:
            statistics['Failed'] += 1
        return False
    if Debug > 2:
        local.output+='Parsing file: '+filename+'\n'

    sizeRegex = re.compile("("+'|'.join(video_size)+")(i|p)?", re.I)

    possibleGroup = search_string[0]
    tagFound=0
    for item in search_string:
        
        # found season and episode tag
        if re.match("[s]?\d?\d[xe]\d\d([xe]\d\d)?$", item, re.I):
            data['season']=re.sub("[s]?0?([1-9]?\d)[xe](\d\d)([xe](\d\d))?", '\\1', item)
            data['episode']=re.sub("[s]?0?([1-9]?\d)[xe](\d\d)([xe](\d\d))?", '\\2', item)
            tagFound = 1
            continue

        # 2CDs video found
        if re.match("^cd\d$", item, re.I):
            data['quality'].append('2cd')
            data['quality'].append(item)
            tagFound = 1
            continue

        # found well-known group
        if item in release_groups:
            data['group'].append(item)
            tagFound = 1
            continue

        # found generic quality tag
        if item in video_quality:
            data['quality'].append(item)
            tagFound = 1
            continue

        # found video resolution tag
        if sizeRegex.match(item):
            if size:
                with lock:
                    statistics['Errors'] += 1
                if Debug > 2:
                    local.output+='! Error, 2 Sizes in file?!?! '+size+' & '+item+'\n'
            data['size'].append(sizeRegex.sub('\\1', item))
            tagFound = 1
            continue
        
        # found Year
        if re.match("\d{4}", item):
            data['year'].append(item)
            tagFound = 1
            continue

        if not tagFound:
            data['videoTitle'].append(item)
            if re.match("^\d$", item):
                tagFound = 2
            continue
            # After a number, consider the rest as subtitle
        elif tagFound == 2:
            data['videoSubTitle'].append(item)
            continue

        # Last unknown is usually the release group
        data['unknown'].append(item)

        continue

    return data

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
                    print(local.output)
                    #print('remaining items: '+str(videosQ.qsize()))
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
            if append_language and not ForceSearch:
                for idx, lang in reversed(list(enumerate(local.wanted_languages))):
                    tmp = os.path.splitext(os.path.join(dirpath, originalFilename))[0] + '.'+lang+'.s*'
                    for sublang in glob.glob(re.sub(r'(?<!\[)\]', '[]]', re.sub(r'\[', '[[]', tmp))):
                        existSubs.append(sublang)
                        if Debug > 1:
                            local.output+='Found a \''+lang+'\' subtitle: '+sublang+'\n'
                        if idx==0:
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
            if not subtitle or subtitle['%'] < confidence_threshold:
                with lock:
                    if local.wanted_languages == preferred_languages:
                        statistics['NoSubs'] += 1
                    else:
                        statistics['NoBest'] += 1

            if not subtitle:
                if local.wanted_languages == preferred_languages:
                    if Debug > -1:
                        local.output+='No subtitles found\n'
                else:
                    if Debug > -1:
                        local.output+='No better subtitles found\n'
                continue
            if subtitle['%'] < confidence_threshold:
                if Debug > -1:
                    local.output+='Only bad subtitles, similiarity: '+str(subtitle['%'])+'\n'
                continue
                
            if ltv.download(subtitle):
                if Debug == 0:
                    local.output+='ed: '+subtitle['language']
                ltv.extract_sub(dirpath, originalFilename, group, size, quality, subtitle['language'])
                if Debug == 0:
                    local.output+=', '+subtitle['release']+'\n'
                continue

            with lock:
                if local.wanted_languages == preferred_languages:
                    statistics['NoSubs'] += 1
                else:
                    statistics['NoBest'] += 1

            if Debug > -1:
                local.output+='Failed to download subtitle: '+subtitle['release']+'\n'

            continue
        
        except queue.Empty:
            #print('Waiting for jobs for '+str(threading.current_thread().getName()))
            if Done:
                return
            time.sleep(random.uniform(1.5, 4.0))
            pass
        except:
            print('print_exc():')
            traceback.print_exc(file=sys.stdout)
            return
        
## Main starts here

if __name__ == '__main__':

    global statistics
    global ltv

    garbage = [x.lower() for x in ['Unrated', 'DC', 'Dual', 'VTV', 'eng', 'subbed', 'artsubs', 'sample', 'ExtraTorrentRG', 'StyLish', 'Release' ]]
    undesired = [x.lower() for x in ['.HI.', '.Impaired.', '.Comentários.', '.Comentarios.' ]]
    video_quality = [x.lower() for x in ['HDTV', 'XviD', 'DivX', 'x264', 'BluRay', 'BRip', 'BRRip', 'BDRip', 'DVDrip', 'DVD', 'AC3', 'DTS', 'TS', 'R5', 'R6', 'DVDScr', 'PROPER', 'REPACK' ]]
    video_size = [x.lower() for x in ['480', '720', '1080']]
    release_groups = [x.lower() for x in known_release_groups]

    preferred_languages = [x.lower() for x in preferred_languages]
    clean_name_from = [x.lower() for x in clean_name_from]
    valid_video_extensions = [x.lower() for x in valid_video_extensions]
    valid_subtitle_extensions = [x.lower() for x in valid_subtitle_extensions]
    
    statistics={'Videos':0, 'NotVideos':0, 'Folders':0, 'Shows':0, 'Movies':0, 'Failed':0, 'Errors':0, 'Best':0, 'DL':0, 'Upg':0, 'NoBest':0, 'NoSubs':0, 'PT':0, 'BR':0, 'EN':0}


    # If variables above are empty, ask from keyboard
    # if len(ltv_username) == 0:
    #     ltv_username = raw_input('Username: ')
    # if len(ltv_password) == 0:
    #     ltv_password = getpass.getpass('Password: ')

    ltv = LegendasTV(ltv_username, ltv_password)

    # Logging in Legendas.TV
    # if not ltv.login():
    #     if Debug > -1:
    #         print '\nPress any key to exit...'
    #     junk = getch()
    #     sys.exit()
    
    # if Debug > 0:
    #     print 'Logged with success!'

    input_string = sys.argv[1:]
    if len(input_string) == 0:
        input_string.append(default_folder)

    input_string.append("-OI")

    videosQ = queue.Queue()

    # Start worker threads here
    for i in range(thread_count):
        t = threading.Thread(target=ltvdownloader, args = (videosQ,), daemon=True)
        t.start()


    if Debug > -1:
        print('Listing files. First results can take a few seconds.\n')

    OriginalInputFinished = False

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

        if originalFilename == '-DI':
            OriginalInputFinished = True
            continue

        if originalFilename == '-f':
            ForceSearch = True
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
            if len(input_string)==2:
                ForceSearch=True
                if Debug > 2:
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

        videosQ.put(os.path.abspath(originalFilename))
    
    while not videosQ.empty():
        time.sleep(1)
    videosQ.join()

    Done=True
    if Debug > 2:
        print('------------------')
    
    #ltv.logout()
    if Debug > -1:
        #print 'Videos: %d, Shows: %d, Movies: %d, NotVideos: %d, Folders: %d' % (statistics['Videos'], statistics['Shows'], statistics['Movies'], statistics['NotVideos'], statistics['Folders'])
        
        print('\n\nFinal statistics:', end="")
        print('Failed!! %d, Errors: %d' % (statistics['Failed'], statistics['Errors'] ))
        
        print('\nFolders analyzed: %d' % (statistics['Folders']))
        print('Movies: %d,  Shows: %d,  NotVideos: %d' % (statistics['Movies'], statistics['Shows'], statistics['NotVideos']))
       
        print('\nSubtitles downloaded: %d, of which %d were upgrades' % (statistics['DL'], statistics['Upg']))
        print('PT: %d,  BR: %d,  EN: %d' % (statistics['PT'], statistics['BR'], statistics['EN']))
        
        print('\nFinal subtitles status in parsed library:')
        print('Best: %d,  Upgradeable: %d,  No Subs: %d' % (statistics['Best'], statistics['NoBest'], statistics['NoSubs']))

    print('\nPress any key to exit...')
    junk = getch()

    sys.exit()
