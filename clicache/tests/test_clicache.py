# Copyright (c) 2014, John A. Brunelle
# All rights reserved.

"""unit tests"""


import os, unittest

os.environ['CLICACHE_DIR'] = os.path.abspath('.clicache')

import clicache
from clicache import cli

import settings


class CLITestCase(unittest.TestCase):
	"""
	test direct suprocess handling
	"""

	funky_string = r"""foo'bar "more" \' \" \n zzz"""
	funky_string_quoted = r"""'foo'\''bar "more" \'\'' \" \n zzz'"""

	#basic runsh()
	def test_runsh_string(self):
		self.assertEqual(cli.runsh('/bin/echo foo'), 'foo\n',
			"runsh() does not work on sh code as a string"
		)
	def test_runsh_list(self):
		self.assertEqual(cli.runsh(['/bin/echo','foo']), 'foo\n',
			"runsh() does not works on an argv list"
		)

	#runsh() with stdinstr
	def test_runsh(self):
		self.assertEqual(cli.runsh('cat', inputstr='foo'), 'foo',
			"runsh does not work on sh code as a string, when providing stdin"
		)
	def test_runsh_with_stdin_list(self):
		"""That runsh_with_stdin() works on argv list."""
		self.assertEqual(cli.runsh(['cat',], inputstr='foo'), 'foo',
			"runsh does not work on an argv list, when providing stdin"

		)

	#basic runsh_i()
	def test_runsh_i_string(self):
		self.assertEqual(
			[line for line in cli.runsh_i("/bin/echo -e 'foo\nbar'")],
			['foo\n', 'bar\n'],
			"runsh_i() does not work on sh code as a string"
		)
	def test_runsh_list(self):
		self.assertEqual(
			[line for line in cli.runsh_i(['/bin/echo', '-e', 'foo\nbar'])],
			['foo\n', 'bar\n'],
			"runsh_i() does not work on an argv list"
		)

	#shquote()
	def test_shquote(self):
		self.assertEqual(
			cli.shquote(self.funky_string),
			self.funky_string_quoted,
			"quoting with shquote() is not the same as quoting manually"
		)
	def test_shquote_runsh(self):
		self.assertEqual(
			cli.runsh('/bin/echo -n %s' % cli.shquote(self.funky_string)),
			self.funky_string,
			"echo is not identity for a funky_string"
		)

	#argv2sh()
	def test_argv2sh(self):
		"""Test that argv2sh creates sensible output.

		Note that there are many valid outputs.  This tests exactly the current
		scheme used, but it's possible that could change, and these tests would
		have to be updated.
		"""
		self.assertEqual(
			cli.argv2sh(['/bin/echo', 'foo bar']),
			r"/bin/echo 'foo bar'",
		)
		self.assertEqual(
			cli.argv2sh(['/bin/echo', "don't fail"]),
			r"/bin/echo 'don'\''t fail'",
		)

	#sherrcheck()
	def test_sherrcheck_status(self):
		"""Test that a non-zero exit status raises an Exception."""
		try:
			cli.runsh('exit 42')
		except cli.ShError, e:
			self.assertEqual(e.returncode, 42,
				"ShError does not include proper returncode"
			)
		else:
			raise AssertionError("bash sh code did not raise proper exception")
	def test_sherrcheck_stderr(self):
		"""Test that non-empty stderr raises an Exception."""
		try:
			cli.runsh('/bin/echo foo >&2')
		except cli.ShError, e:
			self.assertEqual(e.stderr, 'foo\n',
				"ShError does not include proper stderr"
			)
		else:
			raise AssertionError("bash sh code did not raise proper exception")


class HelpersTestCache(unittest.TestCase):
	def test_hash_str(self):
		self.assertEqual(
			clicache._hash('foo'),
			('0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33', 'foo'),
		)
	def test_hash_list(self):
		self.assertEqual(
			clicache._hash(['/bin/echo', 'foo bar']),
			('c8eeb999687585aeac98e3cc884c7cb8767855dd', "/bin/echo 'foo bar'"),
		)
	def test_hash_input(self):
		self.assertEqual(
			clicache._hash(['cat'], 'foo bar'),
			('86cc5f6b73420f8a99d3cda3235284f125637840', "echo 'foo bar' | cat"),
		)


class CLICacheTestCase(unittest.TestCase):
	def test_basics(self):
		#uncached command, warms up the cache
		stdout1 = clicache.runsh('date +%s.%N', maxage=10)

		#import time
		#time.sleep(1)

		#call again, should be served from cache
		stdout2 = clicache.runsh('date +%s.%N', maxage=10)

		self.assertEqual(stdout1, stdout2)


if __name__=='__main__':
	unittest.main()
