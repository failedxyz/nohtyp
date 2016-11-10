from lib.parser2 import Parser
import sys

if len(sys.argv) < 2:
	print("Usage: %s [file]" % sys.argv[0])
	sys.exit(1)

with open(sys.argv[1]) as f:
	code = f.read()
	c_code = Parser(code).parse()
	with open("%s.cpp" % sys.argv[1], "w") as fw:
		fw.write(c_code)