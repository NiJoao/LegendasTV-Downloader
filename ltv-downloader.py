#!/usr/bin/env python
# -*- coding: utf-8 -*-

#### User Configurations ####

## Fill yours
ltv_username = ''
ltv_password = ''

# Folder to scan when no arguments are passed
default_folder = '.'

# Ordered, from: pt, br, en
preferred_languages = ['pt', 'br', 'en']
rename_subtitle = True
append_language = True
# Keeps a subtitle with the same name of the video (hard)linking to the best available subtitle. Occupies no space
hardlink_without_lang_to_best_sub = True

# Set this to 80 or 90 if you just want to download the best languague and subtitle
confidence_threshold = 50 

# Recursivity also becomes active after a '-r' argument
recursive_folders = False

# Rename and clean videos and accompanying files from this garbage-tags 
clean_original_filename = True
clean_name_from = ['VTV', 'DS', 'Unrated', 'www.torentz.3xforum.ro']

# No need to change those, but feel free to add/remove some
valid_subtitle_extensions = ['srt','aas','ssa','sub','smi']
valid_video_extensions = ['avi', 'mkv', 'mp4', 'wmv', 'mov', 'mpg', 'mpeg', '3gp', 'flv']
valid_extension_modifiers = ['!ut', 'part']

known_release_groups = ['lol', '2hd', 'ASAP', 'fever', 'fqm', 'p0w4', 'fov', 'tla', 'refill', 'notv', 'reward', 'bia', 'maxspeed']

Debug = 2    

####### End of user configurations #######

####### Dragons ahead !! #######

import cookielib, urllib2, urllib
import re, os, sys, tempfile, traceback, shutil, getpass
import glob
from zipfile import ZipFile
from time import sleep
from urllib2 import HTTPError, URLError
try:
    from bs4 import BeautifulSoup
except ImportError:
    print 'Python module needed: BeautifulSoup4 / bs4'
    sys.exit()
    
try:
    from rarfile import RarFile
except ImportError:
    print 'Python module needed: rarfile'
    sys.exit()

def CreateHardLink(source, link_name):
    import ctypes
    ch1 = ctypes.windll.kernel32.CreateHardLinkW
    ch1.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
    ch1.restype = ctypes.c_ubyte
    if not ch1(link_name, os.path.join(os.path.dirname(link_name),os.path.basename(source)), 0):
        print '%s --> %s' % ( link_name, os.path.join(os.path.dirname(link_name),os.path.basename(source)) )
        raise ctypes.WinError()
os.link = CreateHardLink

def CreateSymLink(source, link_name):
    import ctypes
    csl = ctypes.windll.kernel32.CreateSymbolicLinkW
    csl.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
    csl.restype = ctypes.c_ubyte
    flags = 0
    if source is not None and os.path.isdir(source):
        flags = 1
    if not csl(link_name, source, flags):
        print '%s --> %s' % (link_name, source)
        raise ctypes.WinError()
os.symlink = CreateSymLink


class LegendasTV:
    class SearchLang:
        PT_BR = '1'
        PT_PT = '10'
        EN = '2'
        ES = '3'
        OTHER = '100'
        ALL = '99'
    
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
        '''LoginForm:
            txtLogin -> max_length(15)
            txtSenha -> max_length(15)
            chkLogin -> 0|1 (keep logged?)
        '''
        login_data = urllib.urlencode({'txtLogin':self.username,'txtSenha':self.password,'chkLogin':0})
        request = urllib2.Request(self.base_url+'/login_verificar.php',login_data)
        try:
            self.response = urllib2.urlopen(request).read()
        except HTTPError, e:
            print e.code
        except URLError, e:
            print e.reason

    def logout(self):
        request = urllib2.Request(self.base_url+'/logoff.php')
        try:
            self.response = urllib2.urlopen(request)
        except HTTPError, e:
            print e.code
        except URLError, e:
            print e.reason
    
    def search(self, videoTitle, videoSubTitle, year, season, episode, group, size, quality):

        searchstr = []
        if season and episode:
            searchstr.append(' '.join(videoTitle)+' '+season+'E'+episode)
            searchstr.append(' '.join(videoTitle)+' '+season+'x'+episode)
            searchstr.append(' '.join(videoTitle)+' '+season+episode)
        else:
            if videoSubTitle and year:
                searchstr.append(' '.join(videoTitle+videoSubTitle+[group]+[year]))
            if videoSubTitle:
                searchstr.append(' '.join(videoTitle+videoSubTitle+[group]))
            if year:
                searchstr.append(' '.join(videoTitle+[group]+[year]))

            searchstr.append(' '.join(videoTitle+[group]))
            searchstr.append(' '.join(videoTitle))

        list_possibilities = []
        
        for vsearch in searchstr:
        
            search_dict = {'txtLegenda':vsearch,'selTipo':1,'int_idioma':LegendasTV.SearchLang.ALL}
            search_data = urllib.urlencode(search_dict)
        
            print '--------'
            print "Searching for subtitles with: "+vsearch
    
            request = urllib2.Request(self.base_url+'/index.php?opcao=buscarlegenda',search_data)
            response = urllib2.urlopen(request)
            page = response.read()
    
            soup = BeautifulSoup(page)


            span_results = soup.find('td',{'id':'conteudodest'}).findAll('span')
            if not span_results:
                print 'No results'
                continue
        
            for span in span_results:
                possibility = {}
                possibility.clear()
                
                # There are 2 SPANs per subtitle on results
                # Don't look at this one for now
                if span.get('class') == ['brls']:
                    continue
                td = span.find('td',{'class':'mais'})
                if not td:
                    print '#### Something went wrong ####'
                    continue
                
                # Get the download ID
                download_id = td.parent.parent['onclick']
                download_id = re.search('(?<=down\(\')[a-z0-9]{20,36}(?=\'\))',download_id).group(0)
                possibility['id'] = download_id
                if not download_id:
                    print 'Couldn\'t get download_id'
                    continue
                
                release = td.parent.parent.find('span',{'class':'brls'}).contents[0]
                possibility['release'] = release.lower()
                try:
                    possibility['release'] = possibility['release'].decode('utf-8', 'ignore')
                except Exception:
                    pass
                try:
                    possibility['release'] = possibility['release'].encode('ascii', 'ignore')
                except Exception:
                    pass
                if not possibility['release']:
                    print 'Couldn\'t get Release'
                    continue
            
                tmp=td.parent.findAll('img')
                for tmp2 in tmp:
                    language=re.search('(?<=flag_)[a-zA-Z]{1,3}(?=\.(gif|jpg|jpeg|png))',tmp2.get('src'), re.I)
                    if language:
                        possibility['language'] = language.group(0).lower()
                        break
                    
                if not possibility['language']:
                    print 'Couldn\'t get Language'
                    continue
                
                downloads = td.contents[5]
                possibility['downloads'] = downloads.lower()
                
                sub_name = td.contents[0].contents[0]
                possibility['sub_name'] = sub_name.lower()
                
                comments = td.contents[7]
                possibility['comments'] = comments.lower()
                
                rating = td.contents[8].contents[1]
                possibility['rating'] = rating.lower()
                
                uploader = td.parent.find('a').contents[0]
                possibility['uploader'] = uploader.encode('ascii', 'ignore')
                
                date = span.findAll('td')[2].contents[0]
                possibility['date'] = date.lower()
                
                possibility['%'] = 100
                
                list_possibilities.append(possibility)
                print 'FOUND!: %s - %s' % (possibility['language'], possibility['release'])
        
        if len(list_possibilities) == 0:
            print 'No subtitles found'
            return False
            
        # Calculate similarity
        for possibility in list_possibilities:
            print '--------'
            print 'Analyzing %s' % (possibility['release'])

            # Filter wanted_languages
            possibility['language'] = possibility['language'].replace('us', 'en')
            if possibility['language'] not in preferred_languages:
                print '0!!, Wrong language: '+possibility['language']+', from: '+str(preferred_languages)
                possibility['%'] = 0
                continue
            
            for index, tmp in enumerate(preferred_languages):
                if tmp == possibility['language']:
                    print '-%d, Language %s at pos %d' % (index*21, possibility['language'], index)
                    possibility['%'] -= 21*index
                    break
            
            # Evaluate name
            for tmp in [j for j in videoTitle]:
                if tmp.lower() not in possibility['sub_name']:
                    print '-15, Missing word: '+tmp+' in name: '+possibility['sub_name']
                    possibility['%'] -= 15*index
        
            # Evaluate season number in name
            if season:
                if season not in possibility['sub_name']:
                    print '-15, Missing Season: '+season+' in name: '+possibility['sub_name']
                    possibility['%'] -= 15*index

            # Filter group
            if group not in possibility['release']:
                print '-20, Correct group not found: '+group
                possibility['%'] -= 20
            
            # Filter size
            if size:
                if size not in possibility['release']:
                    print '-15, Correct size not found: '+size
                    possibility['%'] -= 15
            
            # Evaluate quality
            for tmp in quality:
                if tmp not in possibility['release']:
                    print '-5, Correct quality not found: '+tmp
                    possibility['%'] -= 5

            # Devalue undesired words
            for tmp in undesired:
                if tmp in possibility['release']:
                    print '-2, Undesired found: '+tmp
                    possibility['%'] -= 2

            
        print '------------------'
        final_list = sorted(list_possibilities, key=lambda k: k['%'], reverse=True)
        
        for idx, possibility in enumerate(final_list):
            print "Chance of %d%% to %s, %s" % (possibility['%'], possibility['language'], possibility['release'])
        
        if final_list[0]['language'] not in wanted_languages:
            print '\n-- Best subtitle already present --\n'
            return False
        
        return final_list[0]
        
    def download(self, subtitle):
        download_id = subtitle['id']
        if download_id:
            url_request = self.base_url+'/info.php?d='+download_id+'&c=1'
            
            print 'Downloading %s, %s' % (subtitle['language'], subtitle['release'])
            request =  urllib2.Request(url_request)
            response = urllib2.urlopen(request)
            legenda = response.read()

            self.archivename = os.path.join(self.download_path, str(download_id))
            if 'rar' in response.info().get('Content-Type'):
                self.archivename += '.rar'
            elif 'zip' in response.info().get('Content-Type'):
                self.archivename += '.zip'
            else:
                print 'Couldn\'t detect download MIME TYPE. Not forcing extension'

            f = open(self.archivename, 'wb')
            f.write(legenda)
            #pickle.dump(legenda, f)
            f.close()
            print 'Subtitle downloaded with sucess!'
            print '------------------'
            return True

    def extract_sub(self, dirpath, originalFilename, group, size, quality, language):

        try:
            print "Extracting a",
            if '.zip' in self.archivename:
                print 'zip file...'
                archive = ZipFile(self.archivename)
            else:
                if '.rar' in self.archivename:
                    print 'rar file: %s' % (self.archivename)
                else:
                    print 'GUESSED rar file...'
                archive = RarFile(self.archivename)
                
        except:
            print '! Error, Error opening file.'
            print 'UNRAR must be available on console'
            statistics['Failed'] += 1
            return False
        else:

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
                print 'Analyzing: %s ' % (testname)

                if not testname.endswith(tuple(valid_subtitle_extensions)+('rar', 'zip')):
                    #print 'Non Sub file: ' + srtname
                    continue
                
                print '------------'
                print 'Analyzing: %s ' % (testname)

                    
                if group not in testname:
                    print '-30, Correct Release not found: '+group
                    points-=30
                    
                for tmp in quality:
                    if tmp not in testname:
                        print '-5, Correct quality not found: '+tmp
                        points-=5
                
                for tmp in undesired:
                    if tmp in testname:
                        print '-2, Undesired word found: '+tmp
                        points-=5
                if size:
                    if size not in testname:
                        print '-15, Correct size not found: '+size
                        points-=15
                else:
                    if re.search("("+'|'.join(video_size)+")(i|p)?", testname, re.I):
                        print '-20, Too much size found: ' + srtname.filename
                        points-=20
                
                print 'Adding subtitle file with points %d: %s'  % (points, srtname.filename)
                srts.append([points, srtname])

            print '------------'
            if not srts:
                print '! Error: No valid subs found'
                statistics['Failed'] += 1
                return False
            
            srts.sort(reverse=True)
            extract = []
            
            for idx, [p, n] in enumerate(srts):
                print "Result %d, %d%%: %s" % (idx, p, n.filename)

            #if srts[0][0] > confidence_threshold:
            #    extract.append(srts[0][1])
            extract.append(srts[0][1])

            # maximum=confidence_threshold
            # for idx, [p, n] in enumerate(srts):
            #     print "Result %d, %d%%: %s" % (idx, p, n.filename)
            #     if p >= maximum:
            #         maximum = p
            #         extract.append(n)

            print '------------'
            if len(extract) == 0:
                print '! Error: No subtitles with at least %d%% similarity!' % (confidence_threshold)
                statistics['Failed'] += 1
                return False
                
            ## Extracting
            for fileinfo in extract:
                fileinfo.filename = os.path.basename(fileinfo.filename)

                if fileinfo.filename.endswith(('rar', 'zip')):
                    print 'Recursive extract, RAR was inside: %s' % (fileinfo.filename)
                    archive.extract(fileinfo, self.download_path)
                    self.archivename = os.path.join(self.download_path, fileinfo.filename)
                    ltv.extract_sub(dirpath, originalFilename, group, size, quality, language)
                    continue
                    
                dest_filename = fileinfo.filename

                if len(extract) == 1 and rename_subtitle:
                    dest_filename = os.path.splitext(originalFilename)[0] + os.path.splitext(dest_filename)[1]
                
                if append_language:
                    dest_filename = os.path.splitext(dest_filename)[0]+'.'+language+os.path.splitext(dest_filename)[1]
                

                print 'Extracting subtitle as: %s' % (dest_filename)
                dest_fullFilename = os.path.join(dirpath, dest_filename)
                
                try:
                    # fileinfo.filename = dest_filename
                    # archive.extract(fileinfo, dirpath)

                    fileContents = archive.read(fileinfo)
                    
                    f = open(dest_fullFilename, 'wb')
                    f.write(fileContents)
                    f.close()

                    print 'Subtitle saved with sucess in: %s!' % dirpath
                    if language == 'pt':
                        statistics['PT'] += 1
                    elif language == 'br':
                        statistics['BR'] += 1
                    elif language == 'en':
                        statistics['EN'] += 1
                    if not wanted_languages == preferred_languages:
                        statistics['Upg'] += 1
                        continue
                except Exception:
                    print '! Error, decrompressing!'
                    statistics['Failed'] += 1
                    print 'print_exc():'
                    traceback.print_exc(file=sys.stdout)
                    print
                    print 'print_exc(1):'
                    traceback.print_exc(limit=1, file=sys.stdout)
                    return False

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
    statementClean = re.compile('(?P<sep>\W)[\[\(\{]?'+regex+'[\]\)\}]?(?P=sep)', re.I)
    newname = statementClean.sub('\\1', filename)

    fullNewname = os.path.join(Folder, newname)

    # Sanity check
    if newname == filename:
        print 'Error cleaning original name'
        return filename

    # Cleaning video file
    try:
        os.rename(fullFilename, fullNewname)
        print 'Renamed %s --> %s' % (filename, newname)
    except Exception:
        print '! Error renaming. File in use?'
        return filename

    if not os.path.isfile(fullNewname):
        print '! Error renaming. File in use?'
        return filename
    
    # Cleaning subtitles and other files
    glob_pattern = re.sub(r'(?<!\[)\]', '[]]', re.sub(r'\[', '[[]', os.path.splitext(fullFilename)[0]+'.*'))
    for tmpFile in glob.glob(glob_pattern):
        f = os.path.basename(full)
        tmpNew = statementClean.sub('\\1', tmpFile)
        if n == f:
            print 'Error cleaning this name: %s' % (tmpFile)
        else:
            print 'Found and removing %s in %s' % (regex, tmpFile)
            try:
                os.rename(tmpFile, tmpNew)
            except Exception:
                pass
            if not os.path.isfile(tmpNew):
                print '! Error renaming file: %s' % (tmpFile)
        
    return newname


def createLinkSameName(Folder, Movie, Destination, HardLink=True):

    Movie = os.path.basename(Movie)
    Destination = os.path.basename(Destination)

    linkName = os.path.splitext(Movie)[0] + os.path.splitext(Destination)[1]
    fullLinkName = os.path.join(Folder, linkName)

    try:
        os.remove(fullLinkName)
    except Exception:
        # print 'Error: Couldn\'t remove %s' % (linkName)
        pass

    try:
        if HardLink:
            os.link(Destination, fullLinkName)
        else: # Relative path only when creating symbolic links
            os.symlink(Destination, linkName)

        print 'Linked: %s --> %s' % (linkName, Destination)
    except Exception:
        print '! Error linking %s --> %s' % (linkName, Destination)
        print '! print_exc():'
        traceback.print_exc(file=sys.stdout)
        print

    return


if __name__ == '__main__':
    garbage = [x.lower().decode('utf-8') for x in ['Unrated', 'DC', 'Dual', 'VTV', 'eng', 'subbed', 'artsubs', 'sample', 'ExtraTorrentRG', 'StyLish', 'Release' ]]
    undesired = [x.lower().decode('utf-8') for x in ['.HI.', '.Impaired.', '.Comentários.', '.Comentarios.' ]]
    video_quality = [x.lower() for x in ['HDTV', 'XviD', 'DivX', 'x264', 'Bluray', 'brrip', 'dvdrip', 'AC3', 'DTS', 'ts', 'r5', 'r6', 'DvdScr', 'PROPER', 'REPACK' ]]
    video_size = [x.lower() for x in ['480', '720', '1080']]
    release_groups = [x.lower().decode("utf-8") for x in known_release_groups]

    preferred_languages = [x.lower() for x in preferred_languages]
    clean_name_from = [x.lower().decode('utf-8') for x in clean_name_from]
    valid_video_extensions = [x.lower() for x in valid_video_extensions]
    valid_subtitle_extensions = [x.lower() for x in valid_subtitle_extensions]
    
    statistics={'Videos':0, 'NotVideos':0, 'Folders':0, 'Shows':0, 'Movies':0, 'Failed':0, 'Errors':0, 'Best':0, 'NoUpg':0, 'NoSubs':0, 'PT':0, 'BR':0, 'EN':0, 'Upg':0}


    # If variables above are empty, ask from keyboard
    if len(ltv_username) == 0:
        ltv_username = raw_input('Username: ')
        if len(ltv_password) == 0:
            ltv_password = getpass.getpass('Password: ')

    # Logging in Legendas.TV
    ltv = LegendasTV(ltv_username, ltv_password)
    ltv.login()

    if 'Dados incorretos' in ltv.response:
        print '! Error, wrong login info...'
        sys.exit()

    print '-------------------'
    print 'Logged with success!'

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

        if originalFilename == '-r':
            recursive_folders = True

        print '--------------------------------------'
        
        if os.path.islink(originalFilename):
            print 'Symbolic link ignored!'
            statistics['NotVideos'] += 1
            continue
        
        if os.path.isfile(originalFilename):
            if originalFilename.endswith(tuple(valid_extension_modifiers)):
                originalFilename = os.path.splitext(originalFilename)[0]
            if not originalFilename.endswith(tuple(valid_video_extensions)):
                print 'Not a video file: ' + originalFilename
                statistics['NotVideos'] += 1
                continue
            
        elif os.path.isdir(originalFilename):
            statistics['Folders'] += 1
            if not recursive_folders:
                if len(input_string) > 1:
                    print 'Directory found, recursiveness OFF'
                    continue
                else:
                    print 'Reading whole directory'
            else:
                print 'Recursing directory'
            for files in os.listdir(originalFilename):
                input_string.append(os.path.join(originalFilename, files))
            continue

        else:
            statistics['Failed'] += 1
            print '! Error, Not a file nor a directory?!?! %s' % (originalFilename)
            continue
        
        statistics['Videos'] += 1
        dirpath, originalFilename = os.path.split(os.path.abspath(originalFilename))

        if not dirpath:
            print 'Error, no path!!'
            #dirpath = os.getcwd()
            continue
        
        # print 'Analyzing d: %s, f: %s' % (dirpath, originalFilename)

        # Remove garbage of movie name and accompanying files
        if clean_original_filename:
            originalFilename = cleanAndRenameFile(dirpath, originalFilename)

        wanted_languages = preferred_languages[:]
        
        # check already existing subtitles to avoid re-download
        for idx, lang in reversed(list(enumerate(wanted_languages))):
            if append_language:
                tmp = os.path.splitext(os.path.join(dirpath, originalFilename))[0] + '.'+lang+'.s*'
            else:
                tmp = os.path.splitext(os.path.join(dirpath, originalFilename))[0] + '.s*'
            # Escape square brackets in filenames, Glob's fault...
            glob_pattern = re.sub(r'(?<!\[)\]', '[]]', re.sub(r'\[', '[[]', tmp))
            for subFound in glob.glob(glob_pattern):
                print 'Found existing \'%s\' subtitle: %s' % (lang, subFound) 
                if idx==0:
                    wanted_languages = []
                else:
                    wanted_languages = wanted_languages[0:idx]

        ## Create symlink with the same name as the video, for some players that don't support multiple languages
        if hardlink_without_lang_to_best_sub and (len(wanted_languages) != len(preferred_languages)) and append_language:
            createLinkSameName(Folder=dirpath, Movie=originalFilename, Destination=subFound)

        if len(wanted_languages) == 0:
            statistics['Best'] += 1
            print 'Best subtitles already present'
            continue


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

        # Removing Garbage
        for idx, val in reversed(list(enumerate(search_string))):
            if val in garbage:
                search_string.pop(idx)
                continue
        
        if len(search_string)==0:
            print '! Error, this video is just garbage: %s' % (originalFilename)
            statistics['Failed'] += 1
            continue

        print 'Parsing file: %s' % (originalFilename)

        sizeRegex = re.compile("("+'|'.join(video_size)+")(i|p)?", re.I)

        possibleGroup = search_string[0]
        tagFound=0
        for item in search_string:
            
            # found season and episode tag
            if re.match("[s]?\d?\d[xe]\d\d", item, re.I):
                season=re.sub("[s]?0?([1-9]?\d)[xe](\d\d)", '\\1', item)
                episode=re.sub("[s]?0?([1-9]?\d)[xe](\d\d)", '\\2', item)
                tagFound = 1
                continue

            # 2CDs video found
            if re.match("cd\d", item, re.I):
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
                    print '! Error, 2 Sizes in file?!?! '+size+' & '+item
                    sleep(1)
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
        
        if not videoTitle:
            statistics['Failed'] += 1
            print '! Error, no name detected'
            continue

        if not group:
            group = possibleGroup
            print 'Group not found. Using: %s' % (group)

        if season and episode:
            statistics['Shows'] += 1
        else:
            statistics['Movies'] += 1

        print '------------------'

        print 'Searching for: \n\
        Title: %s\n\
        SubTitle: %s\n\
        year: %d\n\
        season: %s\n\
        episode: %s\n\
        wanted_languages: %s\n\
        group: %s\n\
        size: %s\n\
        quality: %s\n' % (videoTitle, videoSubTitle, year, season, episode, wanted_languages, group, size, quality)
        
        subtitle = ltv.search(videoTitle, videoSubTitle, year, season, episode, group, size, quality)
        if not subtitle:
            if wanted_languages == preferred_languages:
                statistics['NoSubs'] += 1
            else:
                statistics['NoUpg'] += 1
            continue
        
        if subtitle['%'] < confidence_threshold:
            print 'Very bad subtitles, Skipping'
            if wanted_languages == preferred_languages:
                statistics['NoSubs'] += 1
            else:
                statistics['NoUpg'] += 1
            continue
            
        if ltv.download(subtitle):
            ltv.extract_sub(dirpath, originalFilename, group, size, quality, subtitle['language'])
            continue

        if wanted_languages == preferred_languages:
            statistics['NoSubs'] += 1
        else:
            statistics['NoUpg'] += 1
        continue
        print 'Subtitle not found...'
    print '------------------'
    
    ltv.logout()

    print 'Done. \nStatistics:\n'
    print 'Vids: %d, Shows: %d, Movies: %d, NotVideos: %d, Folders: %d' % (statistics['Videos'], statistics['Shows'], statistics['Movies'], statistics['NotVideos'], statistics['Folders'])
    print 'Best: %d, NoUpg: %d, NoSubs: %d' % (statistics['Best'], statistics['NoUpg'], statistics['NoSubs'])
    print 'Upg: %d, PT: %d, BR: %d, EN: %d' % (statistics['Upg'], statistics['PT'], statistics['BR'], statistics['EN'])
    print 'Failed!!!! %d, Errors: %d' % (statistics['Failed'], statistics['Errors'] )

    print
    raw_input('Done...')
#    sleep(3)
