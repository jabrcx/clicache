# Copyright (c) 2014, John A. Brunelle
# All rights reserved.

"""
plain subprocess handling, without caching
"""

import os, select, subprocess, re, logging

re_unquote = re.compile('^[a-zA-Z0-9_\-\.,/]+$')

class ShError(Exception):
	"""An exception from running a subprocess.

	It *may* have the following attributes:
		sh
		returncode
		stderr
	"""
	pass

def shquote(text):
	"""Return the given text as a single, safe string in sh code.

	Note that this leaves literal newlines alone; sh and bash are fine with
	that, but other tools may require special handling.
	"""
	return "'%s'" % text.replace("'", r"'\''")

def argv2sh(argv):
	"""Return the given list of args as a shell command.

	This quotes arguments when appropriate.  For readability, it does not
	always quote them, but it may still quote even when not necessary.
	"""

	sh = ''

	for arg in argv:
		sh += ' '
		if re_unquote.match(arg):
			sh += arg
		else:
			sh += shquote(arg)

	try:
		return sh[1:]
	except IndexError:
		raise ValueError("cannot create shell code from an empty list")



def sherrcheck(sh=None, stderr=None, returncode=None, verbose=True):
	"""Raise an exception if the parameters indicate an error.

	This raises an Exception if stderr is non-empty, even if returncode is
	zero.  Set verbose to False to keep sh and stderr from appearing in the
	Exception.
	"""
	if (returncode is not None and returncode!=0) or (stderr is not None and stderr!=''):
		msg = "shell code"
		if verbose: msg += " [%s]" % repr(sh)
		if returncode is not None:
			if returncode>=0:
				msg += " failed with exit status [%d]" % returncode
			else:
				msg += " killed by signal [%d]" % -returncode
		if stderr is not None:
			if verbose: msg += ", stderr is [%s]" % repr(stderr)
		e = ShError(msg)
		e.sh = sh
		e.returncode = returncode
		e.stderr = stderr
		raise e

def runsh_t(sh, inputstr=None):
	"""Run shell code and return a tuple (stdout, stderr, returncode).

	This does no checking of stderr and returncode.
	"""
	if isinstance(sh, basestring):
		shell=True
	else:
		shell=False

	if inputstr is None:
		stdin = open('/dev/null', 'r')
		communicate_args = ()
	else:
		stdin = subprocess.PIPE
		communicate_args = (inputstr,)

	logging.getLogger('clicache.cli').debug(repr(sh))

	p = subprocess.Popen(
		sh,
		shell=shell,
		stdin=stdin,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE
	)
	stdout, stderr = p.communicate(*communicate_args)
	return stdout, stderr, p.returncode

def runsh(sh, inputstr=None):
	"""Run shell code and return stdout.

	This raises an Exception if exit status is non-zero or stderr is non-empty.
	"""
	stdout, stderr, returncode = runsh_t(sh, inputstr=inputstr)
	sherrcheck(sh, stderr, returncode)
	return stdout

def runsh_i(sh):
	"""Run shell code and yield stdout lines.

	This raises an Exception if exit status is non-zero or stderr is non-empty.
	Be sure to fully iterate this or you will probably leave orphans.
	"""
	BLOCK_SIZE = 4096
	if isinstance(sh, basestring):
		shell=True
	else:
		shell=False

	logging.getLogger('clicache.cli').debug(repr(sh))

	p = subprocess.Popen(
		sh,
		shell=shell,
		stdin=open('/dev/null', 'r'),
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE
	)
	stdoutDone, stderrDone = False, False
	stdout = ''
	stderr = ''
	while not (stdoutDone and stderrDone):
		rfds, ignored, ignored2 = select.select([p.stdout.fileno(), p.stderr.fileno()], [], [])
		if p.stdout.fileno() in rfds:
			s = os.read(p.stdout.fileno(), BLOCK_SIZE)
			if s=='':
				stdoutDone = True
			else:
				i = 0
				j = s.find('\n')
				while j!=-1:
					yield stdout + s[i:j+1]
					stdout = ''
					i = j+1
					j = s.find('\n',i)
				stdout += s[i:]
		if p.stderr.fileno() in rfds:
			s = os.read(p.stderr.fileno(), BLOCK_SIZE)
			if s=='':
				stderrDone = True
			else:
				stderr += s
	if stdout!='':
		yield stdout
	sherrcheck(sh, stderr, p.wait())
