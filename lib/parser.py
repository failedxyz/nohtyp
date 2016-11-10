import json
import string

escapable = {
	"\"": "\"",
	"\'": "\'",
	"\\": "\\",
	"r": "\r",
	"n": "\n",
	"t": "\t",
}

keywords = [
	"def", "print",
]

precedence = {
	"=": 1,
	"||": 2,
	"&&": 3,
	"<": 7, ">": 7, "<=": 7, ">=": 7, "==": 7, "!=": 7,
	"+": 10, "-": 10,
	"*": 20, "/": 20, "%": 20,
}

class Token:
	def __init__(self, **kwargs):
		for key in kwargs:
			setattr(self, key, kwargs[key])

class Node:
	def __init__(self, **kwargs):
		for key in kwargs:
			setattr(self, key, kwargs[key])
	def serialize(self):
		attrs = ["prog", "args", "type", "value", "operator", "left", "right"]
		d = {}
		for k in attrs:
			if hasattr(self, k):
				v = getattr(self, k)
				if isinstance(v, Node):
					d[k] = v.serialize()
				elif isinstance(v, list):
					d[k] = map(lambda c: c.serialize() if isinstance(c, Node) else c, v)
				else:
					d[k] = v
		return d
	def __str__(self):
		return json.dumps(self.serialize(), indent=4)

class InputStream:
	def __init__(self, text):
		self.pos = 0
		self.line = 1
		self.col = 0
		self.text = text
	def eof(self):
		return self.pos >= len(self.text)
	def next(self):
		if not self.eof():
			ch = self.peek()
			self.pos += 1
			if ch == "\n":
				self.line += 1
				self.col = 0
			else:
				self.col += 1
			return ch
	def peek(self):
		return self.text[self.pos]

class Tokenizer:
	def __init__(self, text):
		self.current = None
		self.input = InputStream(text)
	def eof(self):
		return self.input.eof()
	def is_digit(self, ch):
		return ch in "0123456789"
	def is_id(self, ch):
		return self.is_id_start(ch) or ch in string.digits
	def is_id_start(self, ch):
		return ch in string.letters + "_"
	def is_keyword(self, x):
		return x.strip() in keywords
	def is_op_char(self, ch):
		return ch in "+-*/%=&|<>!"
	def is_punc(self, ch):
		return ch in ",;(){}[]"
	def next(self):
		tok = self.current
		self.current = None
		return tok or self.read_next()
	def peek(self):
		if not self.current:
			self.current = self.read_next()
		return self.current
	def read_escaped(self, end):
		escaped = False
		s = ""
		self.input.next()
		while not self.input.eof():
			ch = self.input.next()
			if escaped:
				ec = escapable.get(ch)
				if not ec:
					raise SyntaxError("Unknown symbol \\%s" % ch)
				s += ec
				escaped = False
			elif ch == "\\":
				escaped = True
			elif ch == end:
				break
			else:
				s += ch
		return s
	def read_ident(self):
		_id = self.read_while(self.is_id)
		return Node(type="kw" if self.is_keyword(_id) else "var", value=_id)
	def read_next(self):
		self.read_while(lambda c: c in " \n")
		if self.input.eof():
			return
		ch = self.input.peek()
		if ch == "#":
			self.skip_comment()
			return self.read_next()
		if ch == "\"" or ch == "'":
			return self.read_string(ch)
		if self.is_digit(ch):
			return self.read_number()
		if self.is_id_start(ch):
			return self.read_ident()
		if self.is_punc(ch):
			return Node(type="punc", value=self.input.next())
		if self.is_op_char(ch):
			return Node(type="op", value=self.read_while(self.is_op_char))
		raise SyntaxError("Can't handle symbol %s" % repr(ch))
	def read_number(self):
		has_dot = False
		def func(ch):
			if ch == ".":
				if has_dot: return False
				has_dot = True
				return True
			return self.is_digit(ch)
		number = self.read_while(func)
		return Node(type="num", value=float(number))
	def read_string(self, punc):
		return Node(type="str", value=self.read_escaped(punc))
	def read_while(self, predicate):
		s = ""
		while not self.input.eof() and predicate(self.input.peek()):
			s += self.input.next()
		return s
	def skip_comment(self):
		self.read_while(lambda c: c != "\n")
		self.input.next()

class Parser:
	def __init__(self, text):
		self.input = Tokenizer(text)
	def delimited(self, start, stop, separator, parser):
		a = []
		first = True
		self.skip_punc(start)
		while not self.input.eof():
			if self.is_punc(stop):
				break
			if first:
				first = False
			else:
				self.skip_punc(separator)
			if self.is_punc(stop):
				break
			a.append(parser())
		return a
	def is_kw(self, kw=None):
		tok = self.input.peek()
		return tok if tok and tok.type == "kw" and (not kw or tok.value == kw) else None
	def is_op(self, op=None):
		tok = self.input.peek()
		return tok if tok and tok.type == "op" and (not op or tok.value == op) else None
	def is_punc(self, ch=None):
		tok = self.input.peek()
		return tok if tok and tok.type == "punc" and (not ch or tok.value == ch) else None
	def maybe_binary(self, left, this):
		tok = self.is_op()
		if tok:
			other = precedence[tok.value]
			if other > this:
				self.input.next()
				right = self.maybe_binary(self.parse_atom(), other)
				node = Node(type=("assign" if tok.value == "=" else "binary"), operator=tok.value, left=left, right=right)
				return self.maybe_binary(node, this)
		return left
	def maybe_call(self, expr):
		ex = expr()
		return self.parse_call(ex) if self.is_punc("(") else ex
	def parse_atom(self):
		def func():
			if self.is_punc("("):
				self.input.next()
				ex = self.parse_expression()
				self.skip_punc(")")
				return ex
			if self.is_punc(":"):
				return self.parse_prog()
			if self.is_kw("print"):
				return self.parse_print()
			tok = self.input.next()
			if tok.type in ["var", "num", "str"]:
				return tok
			raise SyntaxError("Unexpected token %s" % repr(self.input.next().serialize()))
		return self.maybe_call(func)
	def parse_call(self, func):
		return Node(type="call", func=func, args=self.delimited("(", ")", ",", self.parse_expression))
	def parse_expression(self):
		return self.maybe_call(lambda: self.maybe_binary(self.parse_atom(), 0))
	def parse_print(self):
		self.input.next()
		node = Node(type="print", args=[self.input.next()])
		while not self.input.eof():
			if not self.is_punc(","):
				break
			node.args.append(self.input.next())
		return node
	def parse_toplevel(self):
		self.root = Node(type="prog", prog=[])
		while not self.input.eof():
			self.root.prog.append(self.parse_expression())
		return self.root
	def parse(self):
		return self.parse_toplevel()
	def skip_punc(self, ch):
		if self.is_punc(ch):
			self.input.next()
		else: raise SyntaxError("Expecting punctuation %s" % repr(ch))