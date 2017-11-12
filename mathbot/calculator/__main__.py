import argparse

import json
import asyncio
import traceback
import sys

from calculator.interpereter import Interpereter
import calculator.parser as parser
import calculator.bytecode as bytecode
import calculator.runtime as runtime
import calculator.errors as errors
from calculator.runtime import wrap_with_runtime


ERROR_TEMPLATE = '''\
On line {line_num} at position {position}
{prev}
{cur}
{carat}
{next}
'''


def main():
	if len(sys.argv) == 1:
		interactive_terminal()
		return
	# Some options, gotta run file
	try:
		args = parse_arguments()
		filename = proc_filename(args.filename)
		code = open(filename).read()
		tokens, ast = parser.parse(code, source_name = filename)
		btc = wrap_with_runtime(bytecode.CodeBuilder(), ast, exportable = args.compile)
		if args.compile:
			print(btc.dump())
			return
		interpereter = Interpereter(btc, trace = args.trace)
		result = interpereter.run()
		print(result)
	except parser.ParseFailed as e:
		print(format_error_place(code, e.position))


def parse_arguments():
	parser = argparse.ArgumentParser()
	parser.add_argument('filename', help = 'The filename of the program to run')
	action = parser.add_mutually_exclusive_group()
	action.add_argument('-t', '--trace', action = 'store_true', help = 'Display details of the program as it is running')
	action.add_argument('-c', '--compile', action = 'store_true', help = 'Dumps the bytecode of the program rather than running it')
	return parser.parse_args()


def run_with_timeout(future, timeout = None):
	loop = asyncio.get_event_loop()
	future = asyncio.wait_for(future, timeout = timeout)
	return loop.run_until_complete(future)


def print_token_parse_caret(to):
	print(' '.join(to.tokens))
	print((sum(map(len, to.tokens[:to.rightmost])) + to.rightmost) * ' ' + '^')


def format_error_place(string, position):
	lines = [''] + string.split('\n') + ['']
	line = 1
	while line < len(lines) - 2 and position > len(lines[line]):
		position -= len(lines[line]) + 1
		line += 1
	return ERROR_TEMPLATE.format(
		line_num = line,
		position = position,
		prev = lines[line - 1],
		cur = lines[line],
		next = lines[line + 1],
		carat = ' ' * position + '^'
	)


def proc_filename(filename):
	if filename[0] == '+':
		return './calculator/scripts/' + filename[1:] + '.c5'
	return filename


def interactive_terminal():

	show_tree = False
	show_parsepoint = False
	builder = bytecode.CodeBuilder()
	runtime = wrap_with_runtime(builder, None)
	interpereter = Interpereter(runtime, builder = builder)
	interpereter.run()
	line_count = 0

	while True:
		line_count += 1
		line = input('> ')
		if line == '':
			break
		elif line == ':tree':
			show_tree = not show_tree
		elif line == ':parsepoint':
			show_parsepoint = not show_parsepoint
		elif line == ':trace':
			interpereter.trace = not interpereter.trace
		elif line == ':cache':
			for key, value in interpereter.calling_cache.values.items():
				print('{:40} : {:20}'.format(str(key), str(value)))
		else:
			try:
				tokens, ast = parser.parse(line, source_name = 'iterm_' + str(line_count))
				if show_tree:
					print(json.dumps(ast, indent = 4))
				ast = {'#': 'program', 'items': [ast, {'#': 'end'}]}
				interpereter.prepare_extra_code({
					'#': 'program',
					'items': [ast]
				})
				# for index, byte in enumerate(bytes):
				# 	print('{:3d} - {}'.format(index, byte))
				result = run_with_timeout(interpereter.run_async(), 5)
				if result is not None:
					print(result)
			except errors.EvaluationError as e:
				dbg = e._linking
				if dbg is None:
					print('No debugging information available for this error.')
					# print('You may wish to open an issue: github.com/DXsmiley/mathbot')
				else:
					print('Runtime error in', dbg['name'])
					print(format_error_place(dbg['code'], dbg['position']))
				print(str(e))
				print('-' * len(str(e)), '\n')
			except parser.ParseFailed as e:
				print('Parse error')
				print(format_error_place(line, e.position))
			except parser.TokenizationFailed as e:
				print('Tokenization error')
				print(format_error_place(line, e.position))
			except Exception as e:
				traceback.print_exc()

main()