# 
# Javbus
# spider.py
# 
# Created by 吴问涵 on 29/01/2017.
# 7:15 PM
# Copyright (c) 2017 吴问涵. All rights reserved.
#

import os
import re
import json
import math
import time
import queue
import random
from multiprocessing import Pool
from multiprocessing import Manager
from multiprocessing import cpu_count

import requests
import argparse
from bs4 import BeautifulSoup
from progress.bar import ShadyBar

page_url = 'http://www.javbus.in/page/{page}'
detail_url = 'http://www.javbus.in/{id}'

sess = requests.Session()
timeout = 300
header = {
    'Referer': 'http://www.javbus.in',
    'Cookie': 'existmag=all',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'
}
total_page = 74

all_info = Manager().list()
exist_id = []

def main(args):
    global exist_id
    if args.input and os.path.exists(args.input):
        with open(args.input, 'r') as f:
            all_info.append(json.load(f))
            exist_id = [info['id'] for info in all_info]
    else:
        print('Did not find last results file {filename}'.format(filename=args.input))

    id_list = generate_id_list(get_studio_dict())
    que = queue.Queue()
    for i in id_list:
        if i not in exist_id:
            que.put(i)

    print('Create process pool, max size = {size} ... '.format(size=args.process), end='')
    p = Pool(args.process)
    print('Done')

    while not que.empty():
        p.apply_async(get_movie, args=(que.get(), ))

    p.close()
    p.join()
    print('All subprocessing done.')

    print('Write data to json file {filename}'.format(filename=args.output))
    with open(args.output, 'w') as f:
        f.write(json.dumps(list(all_info)))

def get_movie(movie_id):
    print('Get   ' + movie_id + '\t info (pid = {pid}) ...'.format(pid=os.getpid()), end='')
    start = time.time()

    url = detail_url.format(id=movie_id)
    sess = requests.Session()
    req = sess.get(url, headers=header, timeout=timeout)

    if req.status_code == 404:
        end = time.time()
        print('Failed(404), runs {runtime:0.2f} seconds.'.format(runtime=(end - start)))
        return

    soup = BeautifulSoup(req.text, 'html.parser')
    info = get_movie_info(soup)
    magnet = get_movie_magnet(soup, info)
    info['magnet'] = magnet

    global all_info
    all_info.append(info)

    end = time.time()
    print('Done, runs {runtime:0.2f} seconds.'.format(runtime=(end-start)))

def generate_id_list(studio_dict):
    l = []
    for studio in studio_dict.keys():
        number = int(re.search(r'(\d+)', studio_dict[studio]).group(1))
        for i in range(1, number+1):
            number_str = calculate_id(i, studio_dict[studio])
            movie_id = '-'.join([studio, number_str])
            l.append(movie_id)
    return l

def get_studio_dict():
    studio_dict = {
        # 'studio': 'lastest id number'
    }

    full_page = ''

    bar = ShadyBar('Get all site info', max=total_page)
    for page in range(1, total_page+1):
        url = page_url.format(page=str(page))
        req = sess.get(url, headers=header, timeout=timeout)
        full_page += req.text
        # sleep(1)
        bar.next()
    bar.finish()

    soup = BeautifulSoup(full_page, 'html.parser')
    movie_boxes = soup.find_all(class_='movie-box')

    print('Generate movie id ... ', end='')
    for movie in movie_boxes:
        tmp = movie['href'].split('/')[-1].split('-')
        if tmp[0] not in studio_dict:
            studio_dict[tmp[0]] = tmp[1]
        else:
            number_in_movie = int(re.search(r'(\d+)', tmp[1]).group(1))
            number_in_dict = int(re.search(r'(\d+)', studio_dict[tmp[0]]).group(1))
            if number_in_dict < number_in_movie:
                studio_dict[tmp[0]] = calculate_id(number_in_movie, studio_dict[tmp[0]])
    print('Done')

    return studio_dict

def calculate_id(no, movie_id):
    number = re.search(r'(\d+)', movie_id).group(1)
    s = str(no).join(movie_id.split(number))
    return '0' * (len(movie_id) - len(s)) + s

def get_movie_info(soup):
    movie_info = soup.find(class_='row movie')
    p = movie_info.find(class_='col-md-3 info').find_all('p')

    info = {
        'id':             p[0].find_all('span')[1].text,
        'title':          movie_info.find(class_='bigImage').img['title'],
        'cover':          movie_info.find(class_='bigImage').img['src'],
        'time':           re.search(r'(\d+-\d+-\d+)', str(p[1])).group(1),
        'length':         re.search(r'(\d+)', str(p[2])).group(1),
        'genre':          [a.text for a in movie_info.find_all('a') if a['href'].startswith('https://www.javbus.in/genre/')],
        'star':           [a.text for a in movie_info.find_all('a') if a['href'].startswith('https://www.javbus.in/star/')],
    }

    return info

def get_movie_magnet(soup, info):
    ajax = 'https://www.javbus.in/ajax/uncledatoolsbyajax.php'
    params = {
        'gid':      re.search(r'var gid = (\d+);', soup.prettify()).group(1),
        'lang':     'zh',
        'img':      info['cover'],
        'uc':       re.search(r'var uc = (\d+);', soup.prettify()).group(1),
        'floor':    math.floor(random.random() * 1e3 + 1),
    }

    ajax_result = sess.get(ajax, params=params, headers=header)
    soup = BeautifulSoup(ajax_result.text, 'html.parser')
    magnet = [tr.find('a')['href'] for tr in soup.find_all('tr') if tr['style'] != 'color:#555;']

    return magnet

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='Specifies the last results file')
    parser.add_argument('-o', '--output', help='Specifies the output file name, DEFAULT javbus.json', default='javbus.json')
    parser.add_argument('-p', '--process', help='Number of Subprocess, DEFAULT cpu_kernel_counts', default=cpu_count())
    args = parser.parse_args()
    main(args)