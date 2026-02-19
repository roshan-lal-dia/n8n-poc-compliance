#!/usr/bin/env python3
import sys, xml.etree.ElementTree as ET

mode = sys.argv[1] if len(sys.argv) > 1 else "ls"
xml_data = sys.stdin.buffer.read()
if not xml_data.strip():
    print("  (empty)")
    sys.exit(0)

try:
    root = ET.fromstring(xml_data)
except ET.ParseError as e:
    print(f"  XML parse error: {e}")
    print(xml_data[:200].decode(errors="replace"))
    sys.exit(1)

ns = ""
if root.tag.startswith("{"):
    ns = root.tag.split("}")[0] + "}"

blobs = root.findall(f".//{ns}Blob")
if not blobs:
    print("  (empty)")
    sys.exit(0)

if mode == "ls":
    for b in blobs:
        name_el = b.find(f"{ns}Name")
        size_el  = b.find(f".//{ns}Content-Length")
        name = name_el.text if name_el is not None else "?"
        size = size_el.text  if size_el  is not None else "?"
        try:
            size_str = f"{int(size):>10,} B"
        except (ValueError, TypeError):
            size_str = f"{size:>10}"
        print(f"  {size_str}  {name}")
elif mode == "tree":
    tree = {}
    for b in blobs:
        name_el = b.find(f"{ns}Name")
        if name_el is None: continue
        parts = name_el.text.strip("/").split("/")
        node = tree
        for p in parts:
            node = node.setdefault(p, {})

    def print_tree(node, indent=0):
        for k in sorted(node.keys()):
            is_file = node[k] == {}
            prefix = ("  " * indent) + ("  " if indent > 0 else "  ")
            icon = "  " if is_file else "  "
            print(f"{prefix}{icon}{k}{'' if is_file else '/'}")
            if not is_file:
                print_tree(node[k], indent + 1)

    print_tree(tree)
