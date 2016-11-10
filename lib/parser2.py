import ast

p2ctype = {
	"int": "int"
}

class Parser:
	@staticmethod
	def get_number_type(n):
		if not float(n).is_integer():
			return "float"
		if abs(n) < 2147483647:
			return "int"
		if abs(n) < 9223372036854775807:
			return "long"
	@staticmethod
	def render_value(v):
		if type(v) is int:
			return str(v)
		elif type(v) is str:
			if len(v) == 1:
				return "'%s'" % v
			return "\"%s\"" % v
	def __init__(self, text):
		self.root = ast.parse(text)
		self.required_libs = set()
	def traverse(self, node):
		if type(node) is list:
			return "".join(list(map(lambda n: self.traverse(n) or "", node)))
		n_type = type(node).__name__
		# print("type:", n_type)
		if n_type == "Add":
			return "+"
		elif n_type == "Assign":
			targets = []
			def get_targets(container):
				for target in container:
					t_type = type(target).__name__
					if t_type == "Name":
						targets.append(target.id)
					elif t_type == "Tuple":
						get_targets(target.elts)
					else:
						raise NotImplementedError("Unknown target type: %s" % t_type)
			get_targets(node.targets)
			values = []
			def get_values(value):
				v_type = type(value).__name__
				if v_type == "list":
					for v in value:
						get_values(v)
				elif v_type == "Num":
					values.append((Parser.get_number_type(value.n), value.n))
				elif v_type == "Str":
					values.append(("string", value.s))
				elif v_type == "Tuple":
					get_values(value.elts)
				else:
					raise NotImplementedError("Unknown value type: %s" % v_type)
			get_values(node.value)
			variables = list(zip(targets, values))
			return "".join("%s %s = %s;" % (_type, name, Parser.render_value(value)) for name, (_type, value) in variables)
		elif n_type == "AugAssign":
			return "%s %s= %s;" % (self.traverse(node.target), self.traverse(node.op), self.traverse(node.value))
		elif n_type == "BinOp":
			return "%s %s %s" % (self.traverse(node.left), self.traverse(node.op), self.traverse(node.right))
		elif n_type == "BoolOp":
			return self.traverse(node.op).join(map(self.traverse, node.values))
		elif n_type == "Call":
			args = []
			for arg in node.args:
				args.append(self.traverse(arg))
			func_name = self.traverse(node.func)
			if func_name == "print":
				self.required_libs.add("iostream")
				return "cout << %s << endl;" % " << ".join(args)
			return "%s(%s)" % (self.traverse(node.func), ", ".join(args))
		elif n_type == "Compare":
			return "%s %s %s" % (self.traverse(node.left), self.traverse(node.ops[0]), self.traverse(node.comparators[0]))
		elif n_type == "Eq":
			return "=="
		elif n_type == "Expr":
			return self.traverse(node.value)
		elif n_type == "For":
			print("FOR", node._fields)
			print(node.target.id)
			print(self.traverse(node.iter))
			init, term, step = "abc"
			return "for(%s;%s;%s) {%s}" % (init, term, step, self.traverse(node.body))
		elif n_type == "FunctionDef":
			return_type = p2ctype.get(node.returns.id)
			name = node.name
			args = ", ".join("%s %s" % (p2ctype.get(arg.annotation.id), arg.arg) for arg in (node.args.args))
			return "%s %s(%s) {%s}" % (return_type, name, args, self.traverse(node.body))
		elif n_type == "If":
			s = "if (%s) {%s}" % (self.traverse(node.test), self.traverse(node.body))
			if len(node.orelse) > 0:
				s += " else {%s}" % self.traverse(node.orelse[0])
			return s
		elif n_type == "Lt":
			return "<"
		elif n_type == "Mod":
			return "%"
		elif n_type == "Module":
			code = ""
			for subnode in node.body:
				subcode = self.traverse(subnode)
				if subcode:
					code += subcode
			return code
		elif n_type == "Name":
			return node.id
		elif n_type == "Num":
			return str(node.n)
		elif n_type == "Or":
			return "||"
		elif n_type == "Return":
			return "return %s;" % self.traverse(node.value)
		elif n_type == "While":
			return "while (%s) {%s}" % (self.traverse(node.test), self.traverse(node.body));
		else:
			raise NotImplementedError("Unknown node type: %s" % n_type)
	def parse(self):
		body = self.traverse(self.root)
		includes = "\n".join("#include <%s>" % lib for lib in list(self.required_libs))
		includes += "\nusing namespace std;"
		return includes + body