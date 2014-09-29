# Copyright (c) 2014, John A. Brunelle
# All rights reserved.

"""
cache entries are timestamped by the time at which the command finishes

example disk layout for 'echo foo':
	.clicache/
	|-- 9f168d2f8df57c83626cf6026658c6adba47c759  #sha1 hash of 'echo foo'
	|   |-- r           #'echo foo' (reverse of the hash)
	|   |-- t           #1411917928.491704 (time when the command finished)
	|   |-- stdout      #'foo'
	|   |-- stderr      #''
	|   `-- returncode  #0
	`-- ...

some usage strategies:

* to avoid cache misses, have another process looping and keeping the cache hot
"""

import sys, os, errno, time, hashlib, uuid, shutil, logging

import settings


#--- setup logging

import logging
#(logging.NullHandler was introduced in 2.7, and this code is 2.6 compatible)
class NullHandler(logging.Handler):
	def emit(self, record):
		pass
logging.getLogger('clicache').addHandler(NullHandler())


#--- constants

FNAME_r = 'r'
FNAME_t = 't'
FNAME_stdout = 'stdout'
FNAME_stderr = 'stderr'
FNAME_returncode = 'returncode'


#--- exceptions

class CacheMiss(Exception): pass


#--- internal helpers

def _hash(sh, inputstr=None):
	"""Return a (hash, reverse) tuple for the given inputs.

	The given sh may be a list of exec args or string of shell code.  The
	returned reverse is the corresponding string of shell code, but it is only
	for dubugging help -- it's not meant to be actually used!
	"""

	#if given an args list, convert to shell code string
	if not isinstance(sh, basestring):
		r = cli.argv2sh(sh)
	else:
		r = sh

	#if givin stdin string, add it to the hash input
	if inputstr is not None:
		r = 'echo %s | %s' % (cli.shquote(inputstr), r)

	hobj = hashlib.sha1()
	hobj.update(r)

	return hobj.hexdigest(), r

def _hash2dir(h):
	"""Return the absolute directory hierarchy list for the hash.

	The returned list starts with CLICACHE_DIR.
	"""
	return os.path.join(settings.CLICACHE_DIR, h[:2], h[2:4], h)

def _cache(h, r, t, stdout, stderr, returncode):
	"""Add an entry to the cache, if appropriate.

	This will replace the existing entry, if present and older.  If there
	exists a newer entry, this leaves it there and drops the given entry.
	"""

	#--- create the base directory for this cli invocation (hash), if necessary

	basedir = _hash2dir(h)

	#make it (it may already exist)
	try:
		os.makedirs(basedir)
	except OSError, e:
		if e.errno != errno.EEXIST: raise  #(we're implementing mkdir -p)


	#--- create and write the cache content for this result, in a new canonical path

	id = str(uuid.uuid1())

	#this is a new uuid'ed name, and no other processors should try to delete
	#or mess with it, since it's not yet the target of the `current` symlink

	new_canonical = os.path.join(basedir, id)
	os.mkdir(new_canonical)

	open(os.path.join(new_canonical,FNAME_t),'w').write('%.6f' % time.time())
	open(os.path.join(new_canonical,FNAME_r),'w').write(r)
	open(os.path.join(new_canonical,FNAME_stdout),'w').write(stdout)
	open(os.path.join(new_canonical,FNAME_stderr),'w').write(stderr)
	open(os.path.join(new_canonical,FNAME_returncode),'w').write('%d' % returncode)


	#--- update (or create) the `current` symlink -- point it to this new canonical directory

	#it's possible this sets current to something older

	#create a symlink to use for an atomic rename
	tmp_symlink = 'current.' + id
	os.symlink(id, os.path.join(basedir,tmp_symlink))

	#get current (now old) canonical path
	old_canonical = None
	try:
		old_canonical = os.path.join(basedir, os.readlink(os.path.join(basedir,'current')))
	except OSError, e:
		if e.errno == errno.ENOENT:
			#there is no `current` symlink target to have to clean up
			pass
		else:
			raise

	#atomic rename of that symlink, setting `current` (works even if `current`
	#doesn't yet exist.
	os.rename(os.path.join(basedir,tmp_symlink), os.path.join(basedir,'current'))

	#remove old cache results (give it a try, ignore errors)
	if old_canonical is not None:
		shutil.rmtree(old_canonical, ignore_errors=True)

def _cached_runsh(h, maxage=-1):
	"""Return (stdout, stderr, returncode) from cache.

	Raises CacheMiss if not in cache.
	"""

	#--- get the cache directory

	try:
		canonical = os.path.join(
			_hash2dir(h),
			os.readlink(os.path.join(_hash2dir(h),'current')),
		)
	except OSError, e:
		if e.errno == errno.ENOENT:
			msg = 'cache miss: %s: %s' % (h, "no entry in cache")
			logging.getLogger('clicache').debug(msg)
			raise CacheMiss(msg)


	#--- get handles on open files

	#do so quickly, in case some other process tries to delete this current
	#cache entry with its own newer one (relying on deleted files still being
	#usable once open); keep retrying until can get a handle on a consistent
	#set (or hit the max)

	good = False
	i = 0
	while i < settings.CLICACHE_MAX_RETRIES:
		try:

			f_t          = open(os.path.join(canonical,FNAME_t),'r')
			f_r          = open(os.path.join(canonical,FNAME_r),'r')
			f_stdout     = open(os.path.join(canonical,FNAME_stdout),'r')
			f_stderr     = open(os.path.join(canonical,FNAME_stderr),'r')
			f_returncode = open(os.path.join(canonical,FNAME_returncode),'r')

			good = True
			break
		except (OSError, IOError):
			raise
			continue
		finally:
			i += 1

	if not good:
		raise Exception("internal error: unable to get a handle on a cache result")


	#--- examine cache entry age

	try:
		t = float(f_t.read())
	except ValueError, e:
		raise Exception("internal error: unexpected timestamp value in cache: %s" % e)
	finally:
		f_t.close()

	if time.time() - t > maxage:
		msg = 'cache miss: %s: %s' % (h, "cache entry is too old")
		logging.getLogger('clicache').debug(msg)
		raise CacheMiss(msg)


	#--- read results and close files

	stdout = f_stdout.read(); f_stdout.close()
	stderr = f_stderr.read(); f_stderr.close()

	try:
		returncode = int(f_returncode.read()); f_returncode.close()
	except ValueError, e:
		raise Exception("internal error: unexpected returncode value in cache: %s" % e)


	#--- return

	msg = 'cache hit: %s' % h
	logging.getLogger('clicache').debug(msg)

	return stdout, stderr, returncode


#--- main

def runsh(sh, inputstr=None, maxage=-1):
	h, r = _hash(sh, inputstr)

	try:
		return _cached_runsh(h, maxage)
	except CacheMiss:
		#run it for real
		stdout, stderr, returncode = cli.runsh_t(sh, inputstr)
		t = time.time()

		#cache it
		_cache(h, r, t, stdout, stderr, returncode)

		#return it from the cache; adjust age so that we're sure to pick it up
		#(i.e. return the result even if it has expired during this processing
		#of it)
		return _cached_runsh(h, maxage=sys.maxint)


if __name__=='__main__':
	settings.CLICACHE_DIR = '.clicache'

	h, r = _hash('echo foo')

	_cache(h, r, time.time(), 'foo', '', 0)
