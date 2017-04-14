import billboard
import pandas as pd
import os
import os.path
import pickle

from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
import time,json
import requests
import re
import random
import urllib
from bs4 import BeautifulSoup
import numpy as np


def get_token():
    auth_url = u'https://accounts.spotify.com/api/token'

    ##### private information #####
    client_id = u'client_id_string_here'
    client_secret = u'client_secret_string_here'
    ##### wipe if publish in public #####
    client = BackendApplicationClient(client_id=client_id)
    oauth = OAuth2Session(client=client)
    token = oauth.fetch_token(token_url=auth_url, client_id=client_id,
        client_secret=client_secret)

    return token

def get_spotify_json(url,token=None):
    if token['expires_at']-time.time() < 100 or not token: # if token less than 100 seconds until expiration
        token = get_token()

    access_token = token['access_token']
    header = {u'Authorization':u'Bearer '+access_token}

    r = requests.get(url,headers=header)
    return r.json(),token

def single_audio_features(track_id,token=None):
    url_head = u'https://api.spotify.com/v1/audio-features/'

    if type(track_id) == str:
        url = url_head + track_id
    else:
        raise TypeError("Track_id should be str!")

    r,token = get_spotify_json(url,token)
    table = pd.DataFrame([r])
    table.drop(['analysis_url','id','track_href','type'],axis=1,inplace=True)
    return table,token

def multiple_audio_features(track_ids,token=None):
    url_head = u'https://api.spotify.com/v1/audio-features?ids='

    if type(track_ids) == list:
        url = url_head + ','.join(track_ids)
    else:
        raise TypeError("Track_ids should be list!")

    rs,token = get_spotify_json(url,token)
    table = pd.DataFrame()
    for r in rs['audio_features']:
        row = pd.DataFrame([r])
        row.drop(['analysis_url','id','track_href','type'],axis=1,inplace=True)
        table = table.append(row)

    return table,token

def chunk_100(series):
    for i in xrange(0,len(series),100):
        yield series[i:(i+100)]

def chunk_50(series): # requesting track info needs smaller size of requests
    for i in xrange(0,len(series),50):
        yield series[i:(i+50)]

def chunk_20(series):
    # used in get_album_date()
    for i in xrange(0,len(series),20):
        yield series[i:(i+20)]

# create database for billboard and MSD songs
def search_uri(title,artist,token=None):
    '''
    title eg.: 'never gonna give you up'
    '''
    # used for MSD songs
    url_head = u'https://api.spotify.com/v1/search?q='
    name = '+'.join(map(urllib.quote,unicode(title,errors='ignore').split(' ')))

    url = url_head+name+'&type=track&market=US&limit=20'

    rs,token = get_spotify_json(url,token)

    if 'tracks' in rs and 'items' in rs['tracks']:
        for result in rs['tracks']['items']:
            if result['album']['artists'][0]['name'].lower() == artist.lower():
                return result['id']
    return None

def get_MSD_tracks(title_artist_set):
    # get title_artist pair from subset namelist
    MSD_tracks = []
    with open('./MSD/MillionSongSubset/AdditionalFiles/subset_unique_tracks.txt') as f:
        for i,line in enumerate(f):
            if len(MSD_tracks) % 100 == 0:
                print i,len(MSD_tracks)
            title,artist = re.split('<SEP>',line.replace('\n',''))[::-1][:2]
            pair = (title.lower(),artist.lower())

            if len(MSD_tracks) <= 4000:
                if pair not in title_artist_set:
                    uri = search_uri(title,artist)
                    if uri:
                        MSD_tracks.append((title,artist,uri))
            else:
                return MSD_tracks
        return MSD_tracks

def get_spotify_names(spotifyIDs):
    '''
    in: [ids,...]
    out: [(title,[artist1,...]),...]
    '''
    # get title,artist names in Spotify version
    names = []

    for chunked_spotifyIDs in chunk_50(spotifyIDs):
        url_head = 'https://api.spotify.com/v1/tracks/?ids='
        detail = ','.join(chunked_spotifyIDs)
        url = url_head+detail
        r = requests.get(url)
        track_lists = r.json()['tracks']

        for track in track_lists:
            title = track['name'].lower()
            artist = [i['name'].lower() for i in track['artists']] # only get first artist for now
            names.append((title,artist))
    return names

def get_lyric(title,artist):
    # get lyric from lyrics.wikia.com
    url_head = u'http://lyrics.wikia.com/wiki/'
    url = url_head+urllib.quote(artist.encode('utf-8'))+':'+urllib.quote(title.encode('utf-8')) #encoding in utf-8 to avoid quote() throwing key error. eg.chanté moore
    r = requests.get(url)
    soup = BeautifulSoup(r.text,'html.parser')
    lyricbox = soup.find('div',class_ = 'lyricbox')
    lyric = re.sub('<.?div.*?>','',str(lyricbox))
    lyric = re.sub('<br/>','.',lyric)
    return lyric

def find_lyric_multiple_artists(ids,spotify_names,lyric_dict):
    '''
    in: ids:[spotifyID1,...]
        spotify_names:[(title,[artist1,...]),...]
    out:
        lyric_dict updated
        leftovers:[spotifyID1,...]
    '''
    leftovers = []
    for i,(title,artists) in enumerate(spotify_names):
        if i % 100 == 0:
            print i
        uri = ids[i]
        j= 0
        while j <= len(artists)-1:
            artist = artists[j]
            lyric = get_lyric(title,artist)
            if lyric != 'None' and uri not in lyric_dict: # if found lyric add that to the lyrics list
                lyric_dict[uri] = lyric
                break
            j += 1
        # if not found lyric for this title,artists
        if lyric == 'None':
            leftovers.append(uri)
    return leftovers

def get_lyric2(title,artist):
    # get lyric from lyrics.wikia.com
    # also look for redirect message
    url_head = u'http://lyrics.wikia.com/wiki/'
    url = url_head+urllib.quote(artist.encode('utf-8'))+':'+urllib.quote(title.encode('utf-8')) #encoding in utf-8 to avoid quote() throwing key error. eg.chanté moore
    r = requests.get(url)
    soup = BeautifulSoup(r.text,'html.parser')
    lyricbox = soup.find('div',class_ = 'lyricbox')

    if lyricbox: # if url has lyricbox
        lyric = re.sub('<.?div.*?>','',str(lyricbox))
        lyric = re.sub('<br/>','.',lyric)
        return lyric
    elif soup.find('div',class_ = 'redirectMsg'): # if url is redirect message page
        href = soup.find('div',class_ = 'redirectMsg').find('a')['href']
        url = u'http://lyrics.wikia.com/'+href
        r = requests.get(url)
        soup = BeautifulSoup(r.text,'html.parser')
        lyricbox = soup.find('div',class_ = 'lyricbox')
        lyric = re.sub('<.?div.*?>','',str(lyricbox))
        lyric = re.sub('<br/>','.',lyric)
        return lyric
    else:
        return 'None'

def find_lyric_multiple_artists2(ids,spotify_names,lyric_dict):
    # use get_lyric2() instead of get_lyric()
    leftovers = []
    for i,(title,artists) in enumerate(spotify_names):
        if i % 100 == 0:
            print i
        uri = ids[i]
        j= 0
        while j <= len(artists)-1:
            artist = artists[j]
            lyric = get_lyric2(title,artist)
            if lyric != 'None' and uri not in lyric_dict: # if found lyric add that to the lyrics list
                lyric_dict[uri] = lyric
                break
            j += 1
        # if not found lyric for this title,artists
        if lyric == 'None':
            leftovers.append(uri)
    return leftovers

def get_lyric3(title,artist):
    # href to url is changed, since some href has /wiki/... instead of wiki/...
    url_head = u'http://lyrics.wikia.com/wiki/'
    url = url_head+urllib.quote(artist.encode('utf-8'))+':'+urllib.quote(title.encode('utf-8')) #encoding in utf-8 to avoid quote() throwing key error. eg.chanté moore
    r = requests.get(url)
    soup = BeautifulSoup(r.text,'html.parser')
    lyricbox = soup.find('div',class_ = 'lyricbox')

    if lyricbox: # if url has lyricbox
        lyric = re.sub('<.?div.*?>','',str(lyricbox))
        lyric = re.sub('<br/>','.',lyric)
        return lyric
    elif soup.find('div',class_ = 'redirectMsg'): # if url is redirect message page
        href = soup.find('div',class_ = 'redirectMsg').find('a')['href']
        url = u'http://lyrics.wikia.com'+href
        r = requests.get(url)
        soup = BeautifulSoup(r.text,'html.parser')
        lyricbox = soup.find('div',class_ = 'lyricbox')
        lyric = re.sub('<.?div.*?>','',str(lyricbox))
        lyric = re.sub('<br/>','.',lyric)
        return lyric
    else:
        return 'None'

def find_lyric_multiple_artists3(ids,spotify_names,lyric_dict):
    # use get_lyric3()
    leftovers = []
    for i,(title,artists) in enumerate(spotify_names):
        if i % 100 == 0:
            print i
        uri = ids[i]
        j= 0
        while j <= len(artists)-1:
            artist = artists[j]
            lyric = get_lyric3(title,artist)
            if lyric != 'None' and uri not in lyric_dict: # if found lyric add that to the lyrics list
                lyric_dict[uri] = lyric
                break
            j += 1
        # if not found lyric for this title,artists
        if lyric == 'None':
            leftovers.append(uri)
    return leftovers

def get_lyric_az(title,artist):
    t = re.sub(r'\W','',title.lower())
    a = re.sub(r'\W','',artist.lower())
    url = 'http://www.azlyrics.com/lyrics/'+a+'/'+t+'.html'
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.75 Safari/537.36'})
    if r.status_code == 200:
        lyricbox = re.findall(r'<!-- Usage of .*?>.*<!-- MxM banner -->',re.sub('\n','',r.text))[0]
        lyrics = re.sub('<br>','.',lyricbox)
        lyrics = re.sub(r'<.*?>',' ',lyrics)
        lyrics = re.sub('\r','',lyrics)
        lyrics = unicode(lyrics).encode('ascii','ignore')
        return lyrics
    return None

def find_lyric_az(ids,spotify_names,lyric_dict):
    leftovers = []
    for i,(title,artists) in enumerate(spotify_names):
        if i % 100 == 0:
            print i
        uri = ids[i]
        j= 0
        while j <= len(artists)-1:
            artist = artists[j]
            lyric = get_lyric3(title,artist)
            if lyric and uri not in lyric_dict: # if found lyric add that to the lyrics list
                lyric_dict[uri] = lyric
                break
            j += 1
        # if not found lyric for this title,artists
        if not lyric:
            leftovers.append(uri)
        time.sleep(0.2)
    return leftovers

# ========= add extra songs I ========= #
def get_track_info(chunked_spotifyIDs,token=None):
    '''
    chuncked_spotifyIDs:chunk_50,track IDs
    '''
    url_head = u'https://api.spotify.com/v1/tracks?ids='

    if type(chunked_spotifyIDs) == list:
        url = url_head + ','.join(chunked_spotifyIDs)
    else:
        raise TypeError("IDs should be list!")

    rs,token = get_spotify_json(url,token)
    results = []
    if 'tracks' in rs:
        for r in rs['tracks']:
            title,uri,pos,artist,album = r['name'],r['uri'],r['track_number'],r['artists'][0]['uri'],r['album']['uri']
            results.append((title,uri,pos,artist,album))
        results = pd.DataFrame(results,columns = ['title','track_uri','track_number','artist','album_uri'])
        return results
    return None

def get_album_tracks(album_id,token=None):
    '''
    in: album_id: u'0FE9t6xYkqWXU2ahLh6D8X'
    out: [(track,track_number,album_uri),...]
    '''
    url_head = u'https://api.spotify.com/v1/albums/'

    url = url_head+album_id+'/tracks?market=US'

    rs,token = get_spotify_json(url,token)

    results = []
    if 'items' in rs:
        for result in rs['items']:
            r = result['uri']
            results.append(r)
        return results #track_uri
    return None

def get_same_album_tracks(spotifyIDs,chosen_songs,token=None):
    '''
    spotifyIDs:album IDs
    chosen_songs: dict of chosen songs,initiated as list of billboard songs
    '''
    results = [] # stores track ids
    for album_id in spotifyIDs:
        tracks = get_album_tracks(album_id,token)

        for i in range(len(tracks)):
            track_id = tracks[i][2].split(':')[-1]
            if track_id not in chosen_songs: # choose a song
                chosen_songs[track_id] = True
                results.append(track_id)
                break
    return results,chosen_songs

# ========= add extra songs II ========= #
def get_similar_artists(artist_id,token=None):
    url_head = u'https://api.spotify.com/v1/artists/'

    url = url_head+artist_id+'/related-artists'

    rs,token = get_spotify_json(url,token)

    results = []
    if 'artists' in rs:
        for result in rs['artists']:
            r = result['uri']
            results.append(r)
        return results
    return None

def get_artist_topsongs(artist_id,token=None):
    url_head = u'https://api.spotify.com/v1/artists/'

    url = url_head+artist_id+'/top-tracks?country=US'

    rs,token = get_spotify_json(url,token)

    results = []
    if 'tracks' in rs:
        for result in rs['tracks']:
            r = result['uri'],result['album']['uri'] #album,album_type,album_uri
            results.append(r)
        return results
    return None

def add_similar_songs(n_add,artist_ids,chosen_song,token=None):
    '''
    artist_ids: [artist_id1,...], not unique list
    chosen_songs: {title_id:True,...}
    '''
    added_song_ids = []
    stop_length = len(chosen_song)+n_add
    while len(chosen_song) < stop_length:
        if len(chosen_song)/100 == 0:
            print len(chosen_song)
        artist_id = artist_ids.pop(0)
        added = False
        similar_artists = get_similar_artists(artist_id,token)
        if similar_artists:
            similar_artist_ids = map(lambda x:x.split(':')[-1],similar_artists)
            for similar_artist_id in similar_artist_ids:
                if not added:
                    top_songs = get_artist_topsongs(similar_artist_id)
                    top_song_ids = map(lambda x:x[0].split(':')[-1],top_songs)
                    for top_song_id in top_song_ids:
                        if top_song_id not in chosen_song:
                            chosen_song[top_song_id] = True
                            added_song_ids.append(top_song_id)
                            added = True
                            break
        else:
            stop_length -= 1
    return added_song_ids

# ========= back up functions(may be used later) ======== #
def search_artist_id(artist,token=None):
    '''
    artist: single artist name, should be from get_spotify_names,i.e. spotify name for artist
    '''
    url_head = u'https://api.spotify.com/v1/search?q='
    name = '+'.join(map(urllib.quote,unicode(artist,errors='ignore').split(' ')))

    url = url_head+name+'&type=artist&market=US&limit=20'

    rs,token = get_spotify_json(url,token)

    if 'artists' in rs and 'items' in rs['artists']:
        for result in rs['artists']['items']:
            if result['name'].lower() == artist.lower():
                return result['id']
    return None

def get_album_date(chunked_spotifyIDs,token=None):
    '''
    chunked_spotifyIDs:[album_id1,...]
    '''
    url_head = u'https://api.spotify.com/v1/albums?ids='
    detail = ','.join(chunked_spotifyIDs)
    url = url_head+detail+'&market=US'
    rs,token = get_spotify_json(url,token)
    if 'albums' in rs:
        dates = []
        for result in rs['albums']:
            dates.append(result['release_date'])
        return dates
    return None

def get_albums_tracks(chunked_spotifyIDs,token=None):
    '''
    in: album_id: u'0FE9t6xYkqWXU2ahLh6D8X'
    out: [trackID1,...]
    '''
    url_head = u'https://api.spotify.com/v1/albums?ids='

    if type(chunked_spotifyIDs) == list:
        url = url_head + ','.join(chunked_spotifyIDs)+'&market=US'
    else:
        raise TypeError("IDs should be list!")

    rs,token = get_spotify_json(url,token)

    results = []
    if 'albums' in rs:
        for album in rs['albums']:
            tracks = album['tracks']['items']
            for track in tracks:
                track_uri,artist_uri,album_uri = track['uri'],track['artists'][0]['uri'],album['uri']
                results.append((track_uri,artist_uri,album_uri))
        return results
    return None

def get_artist_albums(ID,token=None):

    url_head = u'https://api.spotify.com/v1/artists/'

    url = url_head+ID+'/albums?market=US'

    rs,token = get_spotify_json(url,token)

    results = []
    if 'items' in rs:
        for result in rs['items']:
            r = result['name'],result['type'],result['uri'] #album,album_type,album_uri
            results.append(r)
        df = pd.DataFrame(results,columns=['album','type','uri'])
        # get release date for albums
        dates = []
        album_ids = map(lambda x:x.split(':')[-1],df.uri)
        for ids in chunk_20(album_ids):
            d = get_album_date(ids,token)
            dates.extend(d)
        df['release_date'] = dates
        # filter out same first word
        df['first_word'] = map(lambda x:x.split(' ')[0],df.album)
        df.drop_duplicates(subset='first_word',keep='first',inplace=True)
        return df
    return None

# ========= data validity check ========= #
def billboard_crosscheck():
    # check naming differences between billboard and spotify,
    # based on spotifyID in billboard data
    data = pd.read_pickle('Billboard_data')
    data.artist = data.artist.str.lower()
    data.title = data.title.str.lower()
    unique_data = data.loc[:,['title','artist','spotifyID']]
    unique_data.drop_duplicates(subset='spotifyID',keep='first',inplace=True)
    artist_pairs = map(lambda x:re.split(" featuring | \/ | \& | x | feat. ",x),unique_data.artist)
    unique_data.artist = artist_pairs
    names0 = zip(unique_data.title,unique_data.artist)
    ids0 = unique_data.spotifyID.tolist()
    names1 = get_spotify_names(ids0)
    count = 0
    for i in range(len(names1)):
        if names1[i][1][0] != names0[i][1][0]:
            print 'original vs new:',names0[i],names1[i]
            count += 1
    print 'count:',count
