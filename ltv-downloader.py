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

import cookielib, urllib2, urllib
import re, os, sys, tempfile, traceback, shutil, getpass
import glob
from zipfile import ZipFile
# from time import sleep
from urllib2 import HTTPError, URLError

import platform

if(platform.system().lower().find("windows") > -1):
    if Debug > 2:
        print 'Windows system detected'
    import msvcrt
    getch = msvcrt.getch

    def winHardLink(source, link_name):
        import ctypes
        ch1 = ctypes.windll.kernel32.CreateHardLinkW
        ch1.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
        ch1.restype = ctypes.c_ubyte
        if Debug > 2:
            print '%s --> %s' % ( link_name, source )
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
        if Debug > 2:
            print '%s --> %s' % ( link_name, source )
        if not csl(link_name, source, flags):
            raise ctypes.WinError()
    os.symlink = winSymLink

else:
    if Debug > 2:
        print 'Unix system detected'
    import sys, tty
    fd = sys.stdin.fileno()
    tty.setraw(sys.stdin.fileno())
    getch = sys.stdin.read(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print 'Python module needed: BeautifulSoup4 / bs4'
    print '\nPress any key to exit...'
    junk = getch()
    sys.exit()
    
try:
    from rarfile import RarFile
except ImportError:
    print 'Python module needed: rarfile'
    print '\nPress any key to exit...'
    junk = getch()
    sys.exit()



def SameFile(file1, file2):
    try:
        return os.stat(file1) == os.stat(file2)
    except:
        return False
os.path.samefile = SameFile

class LegendasTV:
    
    def __init__(self, ltv_username, ltv_password, download_dir=None):
        if not download_dir:
            download_dir = tempfile.gettempdir()

        self.download_path = os.path.abspath(download_dir)
        self.base_url = 'http://legendas.tv'
        self.username = ltv_username
        self.password = ltv_password

        self.cookieJar = cookielib.CookieJar()
        self.opener= urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookieJar))
        urllib2.install_opener(self.opener)

    def login(self):
        name="data[User][username]"
        '''LoginForm:
            data[User][username] -> max_length(15)
            data[User][password] -> max_length(15)
            chkLogin -> 0|1 (keep logged?)
            _method -> POST
        '''
        login_data = urllib.urlencode({'data[User][username]':self.username, 'data[User][password]':self.password, '_method':'POST'})
        request = urllib2.Request(self.base_url+'/login',login_data)
        try:
            response = urllib2.urlopen(request, timeout=10).read()
        except:
            if Debug > 0:
                print 'login timedout, retrying'
            try:
                response = urllib2.urlopen(request, timeout=10).read()
            except Exception:
                if Debug > -1:
                    print '! Error, login timeout?'
                    print 'print_exc():'
                    traceback.print_exc(file=sys.stdout)
                return False

        if 'Dados incorretos' in response:
            if Debug > -1:
                print '! Error, wrong username or password ...'
            return False

        return True

    def logout(self):
        request = urllib2.Request(self.base_url+'/users/logout')
        try:
            response = urllib2.urlopen(request, timeout=5)
        except:
            return False
        return True
    
    def search(self, videoTitle, videoSubTitle, year, season, episode, group, size, quality):
        if Debug > 2:
            print '------- Searching -------'
        if Debug > 2:
            print 'Title: %s\n\
        SubTitle: %s\n\
        year: %s\n\
        season: %s\n\
        episode: %s\n\
        wanted_languages: %s\n\
        group: %s\n\
        size: %s\n\
        quality: %s\n' % (videoTitle, videoSubTitle, year, season, episode, wanted_languages, group, size, quality)
        
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

            for vsearch in searchstr:
                for ltvpage in ['', '/page:2', '/page:3', '/page:4', '/page:5', '/page:6']:
                    newPossibilities = 0
                    
                    # search_dict = {'q':vsearch,'selTipo':selType,'int_idioma':LegendasTV.SearchLang.ALL}
                    # search_dict = {'q':vsearch,'selTipo':selType,'int_idioma':LegendasTV.SearchLang.ALL}
                    # search_data = urllib.urlencode(search_dict)
                    vsearch = urllib.quote(vsearch)
                    
                    if Debug < 1:
                        print '.',
                    else:
                        print "Searching for subtitles with: "+vsearch+", Type "+str(selType)+" "+ltvpage
                    
                    request = urllib2.Request(self.base_url+'/util/carrega_legendas_busca/termo:'+vsearch+ltvpage)
                    try:
                        response = urllib2.urlopen(request, timeout=15)
                        page = response.read()
                    except:
                        if Debug > 2:
                            print "Search timedout, retrying"
                        try:
                            response = urllib2.urlopen(request, timeout=15)
                            page = response.read()
                        except:
                            if Debug > 2:
                                print "! Error, searching timedout"
                            return False
                    
                    soup = BeautifulSoup(page)

                    div_results = soup.find('div',{'class':'gallery clearfix list_element'}).findAll('article',recursive=False)
                    if not div_results:
                        if Debug > 2:
                            print 'No results'
                        break
                    
                    for span_article in div_results:
                        span_results = span_article.findAll('div',recursive=False)

                        if not span_results:
                            if Debug > 2:
                                print 'No results'
                            continue

                        for span in span_results:

                            try:
                                td = span.find('a').get('href')
                                sub = span.find('a').contents[0]

                                flag = span.find('img').get('src')
                            except:
                                if Debug > 2:
                                    print "! Error parsing result list: "+span.prettify()
                                continue

                            if not td:
                                if Debug > 2:
                                    print '#### Something went wrong ####'
                                continue

                            possibility = {}
                            possibility.clear()
                            
                            newPossibilities += 1

                            # Parse the link
                            tmpregex = re.search('/download/(\w+)/(\w+)/(\w+)',td)

                            if not tmpregex or tmpregex==None or tmpregex.groups<3:
                                print '#### Error parsing link:'+td+' ####'
                                continue

                            # Get the download ID
                            download_id = tmpregex.group(1)
                            release = tmpregex.group(3)

                            if download_id in [x['id'] for x in list_possibilities]:
                                continue

                            possibility['id'] = download_id
                            if not download_id:
                                if Debug > 2:
                                    print 'Couldn\'t get download_id'
                                continue
                            
                            try:
                                release = release.decode('utf-8', 'ignore')
                            except Exception:
                                pass
                            try:
                                release = release.encode('ascii', 'ignore')
                            except Exception:
                                pass

                            possibility['release'] = release.lower()
                            if not possibility['release']:
                                if Debug > 2:
                                    print 'Couldn\'t get Release'
                                continue
                            
                            ## Get the language
                            tmpregex = re.search('/img/\w*/(?:icon|flag)_(\w+)\.(gif|jpg|jpeg|png)',flag)
                            
                            if not tmpregex or tmpregex==None or tmpregex.groups<2:
                                print '#### Error parsing flag: '+flag+' ####'
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
                                    print 'Couldn\'t get Language'
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
                            #possibility['uploader'] = uploader.encode('ascii', 'ignore')
                            
                            #date = span.findAll('td')[2].contents[0]
                            #possibility['date'] = date.lower()
                            
                            possibility['%'] = 100
                            
                            list_possibilities.append(possibility)
                            if Debug > 2:
                                print 'FOUND!: %s - %s' % (possibility['language'], possibility['release'])


                    if Debug > 2:
                        print 'Got results: '+str(newPossibilities)

                    if newPossibilities < 20:
                        break

        if len(list_possibilities) == 0:
            if Debug > 2:
                print 'No subtitles found'
            return False
            
        # Calculate similarity
        for possibility in list_possibilities:
            if Debug > 2:
                print '--------'
            if Debug > 2:
                print 'Analyzing %s' % (possibility['release'])

            # Filter wanted_languages
            possibility['language'] = possibility['language'].replace('us', 'en')
            if possibility['language'] not in preferred_languages:
                if Debug > 2:
                    print '0!!, Wrong language: '+possibility['language']+', from: '+str(preferred_languages)
                possibility['%'] = 0
                continue
            
            for index, tmp in enumerate(preferred_languages):
                if tmp == possibility['language']:
                    if Debug > 2:
                        print '-%d, Language %s at pos %d' % (index*21, possibility['language'], index)
                    possibility['%'] -= 21*index
                    break
            
            # Evaluate name
            for tmp in [j for j in videoTitle]:
                if tmp.lower() not in possibility['sub_name'] and tmp.lower() not in possibility['release']:
                    if Debug > 2:
                        print '-15, Missing word: '+tmp+' in name: '+possibility['sub_name']
                    possibility['%'] -= 15*index
        
            # Evaluate season number in name
            if season:
                if season not in possibility['sub_name'] and season not in possibility['release']:
                    if Debug > 2:
                        print '-15, Missing Season: '+season+' in name: '+possibility['sub_name']
                    possibility['%'] -= 15*index

            # Filter group
            if group not in possibility['release']:
                if Debug > 2:
                    print '-20, Correct group not found: '+group
                possibility['%'] -= 20
            
            # Filter size
            if size:
                if size not in possibility['release']:
                    if Debug > 2:
                        print '-14, Correct size not found: '+size
                    possibility['%'] -= 14
            
            # Evaluate quality
            for tmp in quality:
                denormalizedQuality = deNormalizeQuality(tmp)
                for tmp2 in denormalizedQuality:
                    if tmp2 in possibility['release']:
                        break
                    if tmp2 == denormalizedQuality[-1]:
                        if Debug > 2:
                            print '-5, Correct quality not found: '+tmp2
                        possibility['%'] -= 5

            # Devalue undesired words
            for tmp in undesired:
                if tmp in possibility['release']:
                    if Debug > 2:
                        print '-2, Undesired found: '+tmp
                    possibility['%'] -= 2

        if Debug > 2:
            print '------------------'
        final_list = sorted(list_possibilities, key=lambda k: k['%'], reverse=True)
        
        for idx, possibility in enumerate(final_list):
            if Debug > 2:
                print "Chance %d, %d%%, %s, %s" % (idx, possibility['%'], possibility['language'], possibility['release'])
        
        if final_list[0]['language'] not in wanted_languages:
            if Debug > 2:
                print '\n-- Best subtitle already present --\n'
            return False
        
        return final_list[0]
        
    def download(self, subtitle):
        download_id = subtitle['id']
        if download_id:
            url_request = self.base_url+'/downloadarquivo/'+download_id
            if Debug > 2:
                print '------- Downloading -------'
                print 'Downloading %s, %s' % (subtitle['language'], subtitle['release'])
            request =  urllib2.Request(url_request)
            try:
                response = urllib2.urlopen(request, timeout=20)
                legenda = response.read()
            except:
                if Debug > 2:
                    print "Download timedout, retrying"
                try:
                    response = urllib2.urlopen(request, timeout=20)
                    legenda = response.read()
                except:
                    if Debug > 2:
                        print "! Error, download timedout"
                    return False
            
            if response.info().has_key('Content-Disposition'):
                # If the response has Content-Disposition, we take file name from it
                localName = response.info()['Content-Disposition'].split('filename=')[1]
                if localName[0] == '"' or localName[0] == "'":
                    localName = localName[1:-1]

            if len(localName)>4:
                self.archivename= os.path.join(self.download_path, str(localName))
            else:
                self.archivename = os.path.join(self.download_path, str(download_id))

            if response.info().has_key('Content-Type'):
                if 'rar' in response.info().get('Content-Type'):
                    self.archivename += '.rar'
                elif 'zip' in response.info().get('Content-Type'):
                    self.archivename += '.zip'
                else:
                    if Debug > 2:
                        print 'No download MIME TYPE. Not forcing extension'

            f = open(self.archivename, 'wb')
            f.write(legenda)
            #pickle.dump(legenda, f)
            f.close()
            if Debug > 2:
                print 'Subtitle downloaded with sucess!'
            return True

    def extract_sub(self, dirpath, originalFilename, group, size, quality, language):

        if Debug > 2:
            print '------- Extracting -------'
        if Debug > 3:
            print 'File: '+self.archivename
        if Debug > 2:
            print "Extracting a",
        try:
            archive = ZipFile(self.archivename)
            if Debug > 2:
                print 'zip file...'
        except:
            try:
                archive = RarFile(self.archivename)
                if Debug > 2:
                    print 'rar file...'
            except:
                if Debug > -1:
                    print '! Error, Error opening archive: '+self.archivename
                    print 'UNRAR must be available on console'
                statistics['Failed'] += 1
                return False

        for index, tmp in enumerate(wanted_languages):
            if tmp == language:
                language_compensation = 15*index
                break
            
        files = archive.infolist()
        srts = []

        unique_compensation = 0
        if len(files) == 1:
            unique_compensation = 15

        for srtname in files:
            points = 100 - language_compensation + unique_compensation
            try:
                srtname.filename = srtname.filename.decode('utf-8', 'ignore')
            except Exception:
                pass
            try:
                srtname.filename = srtname.filename.encode('ascii', 'ignore')
            except Exception:
                pass

            testname = srtname.filename.lower()
            if not testname.endswith(tuple(valid_subtitle_extensions)+('rar', 'zip')):
                #if Debug > 2:
                #    print 'Non Sub file: ' + str(srtname)
                continue

            if Debug > 2:
                print 'Analyzing: %s ' % (testname)

            if language not in testname:
                if Debug > 2:
                    print '-1, Language not in FileName: '+language
                points-=1
                
            if group not in testname:
                if Debug > 2:
                    print '-30, Correct Release not found: '+group
                points-=30
                
            for tmp in quality:
                denormalizedQuality = deNormalizeQuality(tmp)
                for tmp2 in denormalizedQuality:
                    if tmp2 in testname:
                        break
                    if tmp2 == denormalizedQuality[-1]:
                        if Debug > 2:
                            print '-5, Correct quality not found: '+tmp2
                        points-=5

            for tmp in undesired:
                if tmp in testname:
                    if Debug > 2:
                        print '-5, Undesired word found: '+tmp
                    points-=5
            if size:
                if size not in testname:
                    if Debug > 2:
                        print '-15, Correct size not found: '+size
                    points-=15
            else:
                if re.search("("+'|'.join(video_size)+")(i|p)?", testname, re.I):
                    if Debug > 2:
                        print '-20, Too much size found: ' + srtname.filename
                    points-=20
            if Debug > 2:
                print 'Adding subtitle file with points %d: %s'  % (points, srtname.filename)
            srts.append([points, srtname])

        if Debug > 2:
            print '-------'
        if not srts:
            if Debug > -1:
                print '! Error: No valid subs found on archive'
            statistics['Failed'] += 1
            return False
        
        srts.sort(reverse=True)
        extract = []
        
        for idx, [p, n] in enumerate(srts):
            if Debug > 2:
                print "Chance %d, %d%%: %s" % (idx, p, os.path.basename(n.filename))

        #if srts[0][0] > confidence_threshold:
        #    extract.append(srts[0][1])
        extract.append(srts[0][1])

        # maximum=confidence_threshold
        # for idx, [p, n] in enumerate(srts):
        #     print "Result %d, %d%%: %s" % (idx, p, n.filename)
        #     if p >= maximum:
        #         maximum = p
        #         extract.append(n)
        if Debug > 2:
            print '------------'
        if len(extract) == 0:
            if Debug > 2:
                print '! Error: No subtitles with at least %d%% similarity!' % (confidence_threshold)
            #statistics['Failed'] += 1
            return False
            
        ## Extracting
        for fileinfo in extract:
            fileinfo.filename = os.path.basename(fileinfo.filename)
            if Debug > 2:
                print 'Extracting: %s' % (fileinfo.filename)

            if fileinfo.filename.endswith(('rar', 'zip')):
                if Debug > 2:
                    print 'Recursive extract, RAR was inside: %s' % (fileinfo.filename)
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
                print 'Extracting subtitle as: %s' % (dest_filename)
            dest_fullFilename = os.path.join(dirpath, dest_filename)
            
            try:
                # fileinfo.filename = dest_filename
                # archive.extract(fileinfo, dirpath)

                fileContents = archive.read(fileinfo)
                
                f = open(dest_fullFilename, 'wb')
                f.write(fileContents)
                f.close()
                if Debug > 2:
                    print 'Subtitle saved with sucess in: %s!' % dirpath
                if language == 'pt':
                    statistics['PT'] += 1
                elif language == 'br':
                    statistics['BR'] += 1
                elif language == 'en':
                    statistics['EN'] += 1
                if not wanted_languages == preferred_languages:
                    statistics['Upg'] += 1
            
            except Exception:
                statistics['Failed'] += 1
                if Debug > -1:
                    print '! Error, decrompressing!'
                    print 'print_exc():'
                    traceback.print_exc(file=sys.stdout)
                    print
                    print 'print_exc(1):'
                    traceback.print_exc(limit=1, file=sys.stdout)
                return False

            if clean_old_language:
                tmp = os.path.splitext(os.path.join(dirpath, originalFilename))[0] + '.??.s*'
                for tmp2 in glob.glob(re.sub(r'(?<!\[)\]', '[]]', re.sub(r'\[', '[[]', tmp))):
                    if Debug > 2:
                        print 'Found: %s' % tmp2
                    if os.path.samefile(dest_fullFilename, tmp2):
                        continue
                    if Debug > 2:
                        print 'Deleted old language: %s' % os.path.basename(tmp2)
                    os.remove(tmp2)

            ## Create hard/SymLink with the same name as the video, for legacy players
            if hardlink_without_lang_to_best_sub and ( not rename_subtitle or append_language):
                createLinkSameName(Folder=dirpath, Movie=originalFilename, Destination=dest_filename)

        return True
        

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
            print 'Error cleaning original name'
        return filename

    # Cleaning video file
    try:
        os.rename(fullFilename, fullNewname)
    except Exception:
        pass

    if not os.path.isfile(fullNewname):
        if Debug > 2:
            print '! Error renaming. File in use? %s' % (filename)
        return filename
    else:
        if Debug > -1:
            print 'Renamed to: %s' % (newname)

    
    # Cleaning subtitles and other files
    glob_pattern = re.sub(r'(?<!\[)\]', '[]]', re.sub(r'\[', '[[]', os.path.splitext(fullFilename)[0]+'.*'))
    for tmpFile in glob.glob(glob_pattern):
        tmpNew = statementClean.sub('', tmpFile)
        if tmpNew == tmpFile:
            if Debug > 2:
                print 'Error cleaning this name: %s' % (tmpFile)
        else:
            if Debug > 2:
                print 'Found and removing %s in %s' % (regex, tmpFile)
            try:
                os.rename(tmpFile, tmpNew)
            except Exception:
                pass

            if not os.path.isfile(tmpNew):
                if Debug > -1:
                    print '! Error renaming subtitles: %s' % (tmpFile)
            else:
                if Debug > -1:
                    print 'Renamed sub to: %s' % (tmpNew)
        
    return newname


def createLinkSameName(Folder, Movie, Destination, HardLink=True):

    Movie = os.path.basename(Movie)
    Destination = os.path.basename(Destination)
    fullDestination = os.path.join(Folder, Destination)

    linkName = os.path.splitext(Movie)[0] + os.path.splitext(Destination)[1]
    fullLinkName = os.path.join(Folder, linkName)
    
    if os.path.samefile(fullDestination, fullLinkName):
        if Debug > 2:
            print 'Link without language already exists'
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
            print 'Linked: %s --> %s' % (linkName, Destination)
    except Exception:
        if Debug > 2:
            print '! Error linking %s --> %s' % (linkName, Destination)
            print '! print_exc():'
            traceback.print_exc(file=sys.stdout)
            print

    return

def normalizeTags(tag):
    tag = tag.lower()
    if tag in ['bluray', 'blueray', 'brip', 'brrip', 'bdrip']:
        return 'bluray'
    if tag in ['dvdrip', 'dvd']:
        return 'dvd'

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

def mergeTags(search_string):
    out_array = []
    jump = False
    for idx, tag in list(enumerate(search_string)):
        if Debug > 2:
            print "Analyzing "+tag
        if jump:
            jump = False
            continue
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
        print "done"
        print str(out_array)


    tag = tag.lower()
    if tag in ['bluray', 'blueray', 'brip', 'brrip', 'bdrip']:
        return 'bluray'
    if tag in ['dvdrip', 'dvd']:
        return 'dvd'

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

def parseFileName(filename):
    garbage = [x.lower().decode('utf-8') for x in ['Unrated', 'DC', 'Dual', 'VTV', 'eng', 'subbed', 'artsubs', 'sample', 'ExtraTorrentRG', 'StyLish', 'Release' ]]
    video_quality = [x.lower() for x in ['HDTV', 'XviD', 'DivX', 'x264', 'BluRay', 'BRip', 'BRRip', 'BDRip', 'DVDrip', 'DVD', 'AC3', 'DTS', 'TS', 'R5', 'R6', 'DVDScr', 'PROPER', 'REPACK' ]]
    video_size = [x.lower() for x in ['480', '720', '1080']]
    release_groups = [x.lower().decode("utf-8") for x in known_release_groups]
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
            print '! Error, this filename is just garbage: %s' % (filename)
        statistics['Failed'] += 1
        return False
    if Debug > 2:
        print 'Parsing file: %s' % (filename)

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
                statistics['Errors'] += 1
                if Debug > 2:
                    print '! Error, 2 Sizes in file?!?! '+size+' & '+item
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

## Main starts here

if __name__ == '__main__':
    garbage = [x.lower().decode('utf-8') for x in ['Unrated', 'DC', 'Dual', 'VTV', 'eng', 'subbed', 'artsubs', 'sample', 'ExtraTorrentRG', 'StyLish', 'Release' ]]
    undesired = [x.lower().decode('utf-8') for x in ['.HI.', '.Impaired.', '.Comentários.', '.Comentarios.' ]]
    video_quality = [x.lower() for x in ['HDTV', 'XviD', 'DivX', 'x264', 'BluRay', 'BRip', 'BRRip', 'BDRip', 'DVDrip', 'DVD', 'AC3', 'DTS', 'TS', 'R5', 'R6', 'DVDScr', 'PROPER', 'REPACK' ]]
    video_size = [x.lower() for x in ['480', '720', '1080']]
    release_groups = [x.lower().decode("utf-8") for x in known_release_groups]

    preferred_languages = [x.lower() for x in preferred_languages]
    clean_name_from = [x.lower().decode('utf-8') for x in clean_name_from]
    valid_video_extensions = [x.lower() for x in valid_video_extensions]
    valid_subtitle_extensions = [x.lower() for x in valid_subtitle_extensions]
    
    statistics={'Videos':0, 'NotVideos':0, 'Folders':0, 'Shows':0, 'Movies':0, 'Failed':0, 'Errors':0, 'Best':0, 'Upg':0, 'NoUpg':0, 'NoSubs':0, 'PT':0, 'BR':0, 'EN':0}


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

    # Parsing all arguments (Files)
    for originalFilename in input_string:
        videoTitle=[]
        videoSubTitle=[]
        season=0
        episode=0
        year=0
        quality=[]
        size=''
        group=''
        dirpath=''

        # Flag to remove garbage from filename in this item
        clean_name = clean_original_filename

        if originalFilename == '-r':
            recursive_folders = True
            continue

        if Debug > 2:
            print '\n------- Parsing -------'
        
        if os.path.islink(originalFilename):
            if Debug > 2:
                print 'Symbolic link ignored! %s' % (os.path.basename(originalFilename))
            statistics['NotVideos'] += 1
            continue
        
        if os.path.isfile(originalFilename):
            if originalFilename.endswith(tuple(valid_extension_modifiers)):
                originalFilename = os.path.splitext(originalFilename)[0]
                clean_name = False # Can't rename

            if not originalFilename.endswith(tuple(valid_video_extensions)):
                if Debug > 2:
                    print 'Not a video file: %s' % (os.path.basename(originalFilename))
                statistics['NotVideos'] += 1
                continue
            
        elif os.path.isdir(originalFilename):
            statistics['Folders'] += 1
            if not recursive_folders:
                if len(input_string) > 1:
                    if Debug > 2:
                        print 'Directory found, recursiveness OFF: %s' % (originalFilename)
                    continue
                else:
                    if originalFilename != '.':
                        recursive_folders = True
                    if Debug > -1:
                        print 'Searching whole directory: %s' % (os.path.abspath(originalFilename))
            else:
                if Debug > 0:
                    print 'Recursing directory: %s' % (os.path.abspath(originalFilename))
            for files in os.listdir(originalFilename):
                input_string.append(os.path.join(originalFilename, files))
            continue

        elif not os.path.exists(originalFilename):
            if Debug > 2:
                print '! Error, file not present! Moved? %s' % (originalFilename)
            continue

        else:
            statistics['Failed'] += 1
            if Debug > -1:
                print '! Error, Not a file nor a directory?!?! %s' % (originalFilename)
            continue
        
        statistics['Videos'] += 1
        dirpath, originalFilename = os.path.split(os.path.abspath(originalFilename))

        if not dirpath:
            statistics['Failed'] += 1
            if Debug > -1:
                print 'Error, no path!!'
            #dirpath = os.getcwd()
            continue
        

        if Debug > -1:
            print '\nAnalyzing: %s' % (originalFilename)

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
            break
        
        wanted_languages = preferred_languages[:]
        
        # Check with language
        if append_language:
            for idx, lang in reversed(list(enumerate(wanted_languages))):
                tmp = os.path.splitext(os.path.join(dirpath, originalFilename))[0] + '.'+lang+'.s*'
                for sublang in glob.glob(re.sub(r'(?<!\[)\]', '[]]', re.sub(r'\[', '[[]', tmp))):
                    existSubs.append(sublang)
                    if Debug > 2:
                        print 'Found a \'%s\' subtitle: %s' % (lang, sublang) 
                    if idx==0:
                        wanted_languages = []
                    else:
                        wanted_languages = wanted_languages[0:idx]
                        
        if subFound and (not sublang or not os.path.samefile(subFound, sublang)):
            statistics['Best'] += 1
            if len(input_string) == 1:
                if Debug > 2:
                    print 'Single argument: Forcing search'
            else:
                if Debug > -1:
                    print 'No-language subtitles already present'
                continue
        
        ## Create symlink with the same name as the video, for some players that don't support multiple languages
        if append_language and hardlink_without_lang_to_best_sub and (len(wanted_languages) != len(preferred_languages)):
            createLinkSameName(Folder=dirpath, Movie=originalFilename, Destination=sublang)
    
        if len(wanted_languages) == 0:
            statistics['Best'] += 1
            if len(input_string) == 1:
                if Debug > 2:
                    print 'Single argument: Forcing search'
            else:
                if Debug > -1:
                    print 'Best-language subtitles already present'
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
                print '! Error, this video is just garbage: %s' % (originalFilename)
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
                    statistics['Errors'] += 1
                    if Debug > 2:
                        print '! Error, 2 Sizes in file?!?! '+size+' & '+item
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
            statistics['Failed'] += 1
            if Debug > -1:
                print '! Error, no name detected'
            continue

        if not group:
            group = possibleGroup
            if Debug > 0:
                print 'Group not known. Using: %s' % (group)

        if season and episode:
            statistics['Shows'] += 1
        else:
            statistics['Movies'] += 1

        if Debug > 2:
            print '------------------'

        subtitle = ltv.search(videoTitle, videoSubTitle, year, season, episode, group, size, quality)
        if not subtitle:
            if wanted_languages == preferred_languages:
                statistics['NoSubs'] += 1
                if Debug > -1:
                    print 'No subtitles found'
            else:
                statistics['NoUpg'] += 1
                if Debug > -1:
                    print 'No better subtitles found'
            continue
        
        if subtitle['%'] < confidence_threshold:
            if Debug > -1:
                print 'Only bad subtitles, similiarity: %d' % (subtitle['%'])
            if wanted_languages == preferred_languages:
                statistics['NoSubs'] += 1
            else:
                statistics['NoUpg'] += 1
            continue
            
        if ltv.download(subtitle):
            ltv.extract_sub(dirpath, originalFilename, group, size, quality, subtitle['language'])
            if Debug > -1:
                print 'Downloaded: %s, %s' % (subtitle['language'], subtitle['release'])
            continue

        if wanted_languages == preferred_languages:
            statistics['NoSubs'] += 1
        else:
            statistics['NoUpg'] += 1

        if Debug > -1:
            print 'Failed to download subtitle: %s' % (subtitle['release'])

        continue
    
    if Debug > 2:
        print '------------------'
    
    ltv.logout()
    if Debug > -1:
        print '\nFinal statistics:'
        #print 'Videos: %d, Shows: %d, Movies: %d, NotVideos: %d, Folders: %d' % (statistics['Videos'], statistics['Shows'], statistics['Movies'], statistics['NotVideos'], statistics['Folders'])
        print 'Movies: %d, Shows: %d, NotVideos: %d, Folders: %d' % (statistics['Movies'], statistics['Shows'], statistics['NotVideos'], statistics['Folders'])
        print 'Best: %d, NoUpg: %d, NoSubs: %d' % (statistics['Best'], statistics['NoUpg'], statistics['NoSubs'])
        print 'Upg: %d, PT: %d, BR: %d, EN: %d' % (statistics['Upg'], statistics['PT'], statistics['BR'], statistics['EN'])
        print 'Failed!!!! %d, Errors: %d' % (statistics['Failed'], statistics['Errors'] )

    print '\nPress any key to exit...'
    junk = getch()
