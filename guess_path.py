#!/usr/bin/env python3
from guessit import guessit
import sys

def tv_path(info):
	return 'tv/' + info['title'] + '/Season ' + str(info['season']).zfill(2) + '/'

def movie_path(info):
	path = 'movies/' + info['title']
	if 'year' in info:
		path += ' (' + str(info['year']) + ')'

	path += '/'
	return path


def guess_path():
	filename = sys.argv[1]
	info = guessit(filename)
	
	is_video = 'video' in info['mimetype']
	media_path = 'media/'

	if is_video == False: return 1

	if info['type'] == 'movie':
		media_path += movie_path(info)
	elif info['type'] == 'episode':
		media_path += tv_path(info)
	else:
	    return 1

	print(media_path)
	return 0


if __name__ == '__main__':
	return guess_path()
