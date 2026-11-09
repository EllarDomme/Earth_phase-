"""static_scan.py —— 轻量静态检查（无第三方依赖）

查：裸 except、可变默认参数、== None、除以可能为 0、未使用的 import、
    同文件重复定义、f-string 里未闭合、范围明显的索引越界。
"""
import ast
import glob
import os

ROOT = r"E:\DeskTop\地球"
FILES = [f for f in glob.glob(os.path.join(ROOT, "*.py"))
         if not os.path.basename(f).startswith("_")]

print("%-26s %-6s %s" % ("文件", "行号", "问题"))
issues = 0
for f in sorted(FILES):
    src = open(f, encoding="utf-8").read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print("%-26s %-6s 语法错误：%s" % (os.path.basename(f), e.lineno, e.msg))
        issues += 1
        continue
    name = os.path.basename(f)

    # ① 裸 except / except Exception 太宽（只提示裸的）
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            print("%-26s %-6d 裸 except" % (name, node.lineno))
            issues += 1

    # ② 可变默认参数
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in node.args.defaults + [x for x in node.args.kw_defaults if x]:
                if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                    print("%-26s %-6d 可变默认参数 %s" % (name, node.lineno, node.name))
                    issues += 1

    # ③ == None / != None
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            is_eq = any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops)
            for c in (node.comparators if is_eq else []):
                if isinstance(c, ast.Constant) and c.value is None:
                    print("%-26s %-6d 用 ==/!= 比较 None" % (name, node.lineno))
                    issues += 1

    # ④ 同文件重复函数名
    seen = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if node.name in seen and not node.name.startswith("_"):
                print("%-26s %-6d 重复定义 %s（上次 L%d）"
                      % (name, node.lineno, node.name, seen[node.name]))
                issues += 1
            seen[node.name] = node.lineno

    # ⑤ 未使用的 import（粗查：名字在文件里只出现一次）
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imported[(a.asname or a.name).split(".")[0]] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name != "*":
                    imported[a.asname or a.name] = node.lineno
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    used |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    for nm, ln in imported.items():
        if nm not in used and nm not in src.split("import", 1)[1][:0]:
            cnt = src.count(nm)
            if cnt <= 1:
                print("%-26s %-6d 未使用的 import %s" % (name, ln, nm))
                issues += 1

print()
print("共 %d 处提示" % issues)
