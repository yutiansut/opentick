#!/usr/bin/env python3

import datetime
import opentick
from six.moves import xrange
import six
import pytz
import time
import logging
import sys

rootLogger = logging.getLogger()
consoleHandler = logging.StreamHandler(sys.stdout)
logFormatter = logging.Formatter(
    '%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s')
consoleHandler.setFormatter(logFormatter)
rootLogger.addHandler(consoleHandler)
rootLogger.setLevel(logging.INFO)

localize = pytz.utc.localize
conn = None


def log(*args):
  six.print_(datetime.datetime.now(), *args)


try:
  conn = opentick.Connection('127.0.0.1', 1116)
  conn.start()
  res = conn.execute('create database if not exists test')
  conn.use('test')
  res = conn.execute(
      'create table if not exists test(sec int, interval int, tm timestamp, open double, high double, low double, close double, vol double, vwap double, primary key(sec, interval, tm))'
  )
  res = conn.execute('delete from test where sec=?', (1,))
  log('records deleted')
  tm = datetime.datetime.now()
  for i in xrange(100):
    n1 = 10
    n2 = 10000
    tm2 = None
    futs = []
    now = datetime.datetime.now()
    for j in xrange(n1):
      for k in xrange(n2):
        ms = j * n2 + k
        tm2 = tm + datetime.timedelta(microseconds=ms)
        futs.append(
            conn.execute_async(
                'insert into test(sec, interval, tm, open, high, low, close, vol, vwap) values(?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (1, i, tm2, 2.2, 2.4, 2.1, 2.3, 1000000, 2.25)))
    now2 = datetime.datetime.now()
    log(str(now2 - now), 'async done')
    for f in futs:
      f.get()
    now3 = datetime.datetime.now()
    log(
        str(now3 - now2), str(now3 - now), i, len(futs),
        'all insert futures get done')
    try:
      futs[0].get(1)
    except Exception as e:
      assert (str(e) == 'Timeout')
    futs = []
    now = datetime.datetime.now()
    for j in xrange(n1):
      args_array = []
      for k in xrange(n2):
        ms = j * n2 + k
        tm2 = tm + datetime.timedelta(microseconds=ms)
        args_array.append([1, i, tm2, 2.2, 2.4, 2.1, 2.3, 1000000, 2.25])
      # the batch size is limited by foundationdb transaction size
      # https://apple.github.io/foundationdb/known-limitations.html
      res = conn.batch_insert_async(
          'insert into test(sec, interval, tm, open, high, low, close, vol, vwap) values(?, ?, ?, ?, ?, ?, ?, ?, ?)',
          args_array)
      futs.append(res)
    now2 = datetime.datetime.now()
    log(str(now2 - now), 'async done')
    for f in futs:
      f.get()
    now3 = datetime.datetime.now()
    log(
        str(now3 - now2), str(now3 - now), i, len(futs),
        'all batch insert futures get done')
    futs = []
    for j in range(i + 1):
      futs.append(
          conn.execute_async(
              'select * from test where sec=1 and interval=? and tm>=? and tm<=?',
              (j, opentick.split_range(tm, tm2, 10))))
    res = []
    for f in futs:
      res += f.get()
    now4 = datetime.datetime.now()
    log(str(now4 - now3), len(res), 'retrieved with ranges')
    assert (len(res) == (i + 1) * n1 * n2)
    assert (res[0][2] == localize(tm))
    assert (res[-1][2] == localize(tm2))
    res = conn.execute(
        'select tm from test where sec=1 and interval=? and tm=?', (i, tm))
    assert (res[0][0] == localize(tm))
    res = conn.execute(
        'select tm from test where sec=1 and interval=? limit -2', (i,))
    assert (len(res) == 2)
    assert (res[0][0] == localize(tm2))
    futs = []
    for j in range(i + 1):
      futs.append(
          conn.execute_async('select * from test where sec=1 and interval=?',
                             (j,)))
    res = []
    for f in futs:
      res += f.get()
    now5 = datetime.datetime.now()
    log(str(now5 - now4), len(res), 'retrieved with async')
    assert (len(res) == (i + 1) * n1 * n2)
    assert (res[0][2] == localize(tm))
    assert (res[-1][2] == localize(tm2))
    if i < 20:
      res = conn.execute('select * from test where sec=1')
      now6 = datetime.datetime.now()
      log(str(now6 - now5), len(res), 'retrieved with one sync')
      assert (len(res) == (i + 1) * n1 * n2)
      assert (res[0][2] == localize(tm))
      assert (res[-1][2] == localize(tm2))
    log()
except opentick.Error as e:
  log(e)
finally:
  if conn: conn.close()
