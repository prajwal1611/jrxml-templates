#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Converter: loan-agreement-secured (1).html (Thymeleaf)  ->  LoanAgreement.jrxml

Produces a JasperReports 6.21 template that reproduces the loan agreement document.
Strategy: walk the Thymeleaf content fragment in document order and emit a single
detail band with vertically-flowing elements (positionType="Float" +
isStretchWithOverflow), matching the conventions used by the other templates in
this repo (SanctionLetterGold.jrxml / kfs_rajasthan.jrxml).
"""

import re
import html as html_mod
from bs4 import BeautifulSoup, NavigableString, Tag

SRC = "loan-agreement-secured (1).html"
OUT = "LoanAgreement.jrxml"

PAGE_W = 595
PAGE_H = 842
MARGIN = 30
CONTENT_W = PAGE_W - 2 * MARGIN  # 535

BODY_FONT = 9
TABLE_FONT = 8
LINE_H = 12          # px per text line for body font
TABLE_LINE_H = 11

# ----------------------------------------------------------------------------
# th:each list configuration
# ----------------------------------------------------------------------------
LIST_CONFIG = {
    "coApplicantList":       {"dataset": "CoApplicantNameDataset",   "string": True,
                              "fields": ["_THIS"]},
    "trancheConditions":     {"dataset": "TrancheConditionDataset",  "string": True,
                              "fields": ["_THIS"]},
    "coApplicantDetailList": {"dataset": "CoApplicantDetailDataset", "string": False,
                              "fields": ["applicantName", "address", "mobile"]},
    "collateralList":        {"dataset": "CollateralDataset",        "string": False,
                              "fields": ["ownerName", "propertyName", "propertyAddress",
                                         "totalAmount", "mobile"]},
    "trancheDetails":        {"dataset": "TrancheDetailDataset",     "string": False,
                              "fields": ["trancheNumber", "trancheAmount", "trancheCondition"]},
    "installments":          {"dataset": "InstallmentDataset",       "string": False,
                              "fields": ["installmentNo", "principalOutstanding",
                                         "principalDue", "interestDue", "installmentAmount"]},
}

INLINE_TAGS = {"span", "strong", "b", "i", "em", "u", "sup", "sub", "a", "font", "br", "label"}

# collected scalar parameter names
scalar_params = set()

_uuid_counter = [0]
def uuid():
    _uuid_counter[0] += 1
    n = _uuid_counter[0]
    return "abcd0000-0000-0000-0000-%012d" % n


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def xml_attr_escape(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))

def java_str_literal(s):
    """Quote a python string as a Java string literal (content already html-ready)."""
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\n", "\\n").replace("\r", "").replace("\t", " ")
    return '"' + s + '"'

def html_text_escape(s):
    """Escape a raw text node for use inside Jasper html markup."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def collapse_ws(s):
    return re.sub(r"\s+", " ", s)

TH_FIELD_RE = re.compile(r"\$\{\s*([A-Za-z0-9_]+)\??\.?([A-Za-z0-9_]*)\s*\}")
TH_TEMPLATE_RE = re.compile(r"\$\{\s*templateData\??\.([A-Za-z0-9_]+)\s*\}")


def value_expr_for_th(expr, ctx):
    """Convert a Thymeleaf expression like ${templateData?.amount} or ${var?.prop}
    into a Java sub-expression returning a String (null-safe)."""
    expr = expr.strip()
    m = TH_TEMPLATE_RE.search(expr)
    if m:
        name = m.group(1)
        scalar_params.add(name)
        return '($P{%s}==null?"":String.valueOf($P{%s}))' % (name, name)
    # loop variable expression
    m = TH_FIELD_RE.search(expr)
    if m:
        var, prop = m.group(1), m.group(2)
        if ctx.get("loopvar") and var == ctx["loopvar"]:
            field = prop if prop else "_THIS"
            return '($F{%s}==null?"":String.valueOf($F{%s}))' % (field, field)
        # nested templateData missed above; fall back
        if var == "templateData" and prop:
            scalar_params.add(prop)
            return '($P{%s}==null?"":String.valueOf($P{%s}))' % (prop, prop)
    return '""'


# ----------------------------------------------------------------------------
# inline content -> java expression (with html markup tags preserved)
# ----------------------------------------------------------------------------
def inline_parts(node, ctx, parts):
    """Append ('lit', text) or ('expr', javaexpr) tuples for the inline content."""
    if isinstance(node, NavigableString):
        txt = collapse_ws(str(node))
        if txt:
            parts.append(("lit", html_text_escape(txt)))
        return

    if not isinstance(node, Tag):
        return

    name = node.name.lower()

    # Thymeleaf value spans
    th_text = node.get("th:text")
    th_utext = node.get("th:utext")
    if th_text is not None:
        parts.append(("expr", value_expr_for_th(th_text, ctx)))
        return
    if th_utext is not None:
        # unescaped -> value may already contain html (e.g. emiDate "5<sup>th</sup>")
        parts.append(("expr", value_expr_for_th(th_utext, ctx)))
        return

    if name == "br":
        parts.append(("lit", "<br/>"))
        return

    # styling wrappers
    open_tag = close_tag = ""
    style = (node.get("style") or "").lower()
    classes = " ".join(node.get("class") or []).lower()
    if name in ("strong", "b"):
        open_tag, close_tag = "<b>", "</b>"
    elif name in ("i", "em"):
        open_tag, close_tag = "<i>", "</i>"
    elif name == "u":
        open_tag, close_tag = "<u>", "</u>"
    elif name == "sup":
        open_tag, close_tag = "<sup>", "</sup>"
    elif name == "sub":
        open_tag, close_tag = "<sub>", "</sub>"
    elif "underline" in classes or "text-decoration: underline" in style or "text-decoration:underline" in style:
        open_tag, close_tag = "<u>", "</u>"

    if open_tag:
        parts.append(("lit", open_tag))
    for child in node.children:
        inline_parts(child, ctx, parts)
    if close_tag:
        parts.append(("lit", close_tag))


def parts_to_expr(parts):
    """Merge consecutive literals and build a Java concatenation expression."""
    merged = []
    for kind, val in parts:
        if kind == "lit" and merged and merged[-1][0] == "lit":
            merged[-1] = ("lit", merged[-1][1] + val)
        else:
            merged.append([kind, val])
    pieces = []
    for kind, val in merged:
        if kind == "lit":
            if val.strip() == "" and len(pieces) == 0:
                continue
            pieces.append(java_str_literal(val))
        else:
            pieces.append(val)
    if not pieces:
        return '""'
    return " + ".join(pieces)


def expr_is_empty(expr):
    return expr.strip() in ('""', "")


def inline_expr(node, ctx, prefix_lit=""):
    parts = []
    if prefix_lit:
        parts.append(("lit", prefix_lit))
    if isinstance(node, list):
        for n in node:
            inline_parts(n, ctx, parts)
    else:
        inline_parts(node, ctx, parts)
    return parts_to_expr(parts)


def estimate_text_height(parts_text_len, width, font=BODY_FONT, line_h=LINE_H, min_lines=1):
    cpl = max(8, int(width / (font * 0.50)))
    lines = max(min_lines, (parts_text_len // cpl) + 1)
    return lines * line_h + 4


def approx_len_of_parts(node, ctx):
    parts = []
    if isinstance(node, list):
        for n in node:
            inline_parts(n, ctx, parts)
    else:
        inline_parts(node, ctx, parts)
    total = 0
    for kind, val in parts:
        if kind == "lit":
            total += len(re.sub(r"<[^>]+>", "", val))
        else:
            total += 14  # rough width for a substituted value
    return total


# ----------------------------------------------------------------------------
# Layout container
# ----------------------------------------------------------------------------
class Layout:
    def __init__(self, x0, width):
        self.x0 = x0
        self.width = width
        self.y = 0
        self.elements = []
        self.meta = []          # parallel list of (start_y, height) per top-level element

    def emit(self, xml, height=0):
        self.meta.append((self.y, height))
        self.elements.append(xml)
        self.y += height


def text_field(lay, x, width, expr, font=BODY_FONT, bold=False, italic=False,
               align="Justified", height=None, text_len=None, line_h=LINE_H,
               valign="Top", box=None, float_pos=True):
    if height is None:
        if text_len is None:
            text_len = 40
        height = estimate_text_height(text_len, width, font, line_h)
    boldattr = ' isBold="true"' if bold else ""
    italicattr = ' isItalic="true"' if italic else ""
    pos = ' positionType="Float"' if float_pos else ""
    boxxml = box or ""
    xml = (
        '<textField isStretchWithOverflow="true" isBlankWhenNull="true" textAdjust="StretchHeight">'
        '<reportElement%s x="%d" y="%d" width="%d" height="%d" uuid="%s"/>'
        '%s'
        '<textElement textAlignment="%s" verticalAlignment="%s" markup="html">'
        '<font fontName="SansSerif" size="%d"%s%s/></textElement>'
        '<textFieldExpression><![CDATA[%s]]></textFieldExpression>'
        '</textField>'
    ) % (pos, x, lay.y, width, height, uuid(), boxxml, align, valign, font,
         boldattr, italicattr, expr)
    lay.emit(xml, height)


def emit_break(lay):
    lay.emit('<break><reportElement positionType="Float" x="0" y="%d" width="%d" height="1" uuid="%s"/></break>'
             % (lay.y, lay.width, uuid()), 1)


def emit_hr(lay, x, width):
    lay.emit('<line><reportElement positionType="Float" x="%d" y="%d" width="%d" height="1" uuid="%s"/>'
             '<graphicElement><pen lineWidth="0.75"/></graphicElement></line>'
             % (x, lay.y, width, uuid()), 4)


# ----------------------------------------------------------------------------
# list rendering (ol/ul)
# ----------------------------------------------------------------------------
def roman(n):
    vals = [(1000,"m"),(900,"cm"),(500,"d"),(400,"cd"),(100,"c"),(90,"xc"),
            (50,"l"),(40,"xl"),(10,"x"),(9,"ix"),(5,"v"),(4,"iv"),(1,"i")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out

def list_marker(idx, list_type):
    if list_type == "decimal":
        return "%d." % idx
    if list_type == "lower-alpha":
        return "%c)" % (ord('a') + idx - 1)
    if list_type == "upper-alpha":
        return "%c." % (ord('A') + idx - 1)
    if list_type == "lower-roman":
        return roman(idx) + "."
    if list_type == "upper-roman":
        return roman(idx).upper() + "."
    if list_type in ("disc", "circle", "square"):
        return "\u2022"
    return "%d." % idx


def get_list_type(ol):
    style = (ol.get("style") or "").lower()
    m = re.search(r"list-style-type:\s*([a-z\-]+)", style)
    if m:
        return m.group(1)
    return "disc" if ol.name == "ul" else "decimal"


def render_list(ol, ctx, lay, indent):
    list_type = get_list_type(ol)
    try:
        idx = int(ol.get("start", "1"))
    except ValueError:
        idx = 1
    child_indent = indent + 22
    for li in ol.find_all("li", recursive=False):
        marker = list_marker(idx, list_type)
        idx += 1
        # split li children into leading inline + nested blocks
        inline_buf = []
        nested = []
        for child in li.children:
            if is_block(child):
                nested.append(child)
            else:
                inline_buf.append(child)
        expr = inline_expr(inline_buf, ctx, prefix_lit="<b>" + marker + "</b>&nbsp;")
        tlen = approx_len_of_parts(inline_buf, ctx) + len(marker) + 1
        x = lay.x0 + child_indent
        w = lay.width - child_indent
        if not expr_is_empty(expr) or not nested:
            text_field(lay, x, w, expr, text_len=tlen)
        for nb in nested:
            process_block(nb, ctx, lay, child_indent)
        lay.y += 2


# ----------------------------------------------------------------------------
# table rendering
# ----------------------------------------------------------------------------
def cell_colspan(td):
    try:
        return max(1, int(td.get("colspan", "1")))
    except ValueError:
        return 1

def get_rows(table):
    rows = []
    for child in table.children:
        if isinstance(child, Tag):
            if child.name == "tr":
                rows.append(child)
            elif child.name in ("thead", "tbody", "tfoot"):
                # a thead may contain bare <th> (header row) or <tr>
                trs = [c for c in child.children if isinstance(c, Tag) and c.name == "tr"]
                if trs:
                    rows.extend(trs)
                else:
                    ths = [c for c in child.children if isinstance(c, Tag) and c.name in ("th", "td")]
                    if ths:
                        rows.append(child)  # treat the thead itself as a row container
    return rows

def row_cells(row):
    return [c for c in row.children if isinstance(c, Tag) and c.name in ("td", "th")]


def compute_num_cols(table):
    n = 1
    for row in get_rows(table):
        total = sum(cell_colspan(c) for c in row_cells(row))
        n = max(n, total)
    return n


def cell_box(extra=""):
    return ('<box leftPadding="3" rightPadding="3" topPadding="2" bottomPadding="2">'
            '<topPen lineWidth="0.75" lineColor="#000000"/>'
            '<leftPen lineWidth="0.75" lineColor="#000000"/>'
            '<bottomPen lineWidth="0.75" lineColor="#000000"/>'
            '<rightPen lineWidth="0.75" lineColor="#000000"/></box>')


def find_theach(node):
    """Return (var, listname) if node carries th:each, else None."""
    val = node.get("th:each")
    if not val:
        return None
    m = re.match(r"\s*([A-Za-z0-9_]+)\s*:\s*\$\{\s*templateData\??\.([A-Za-z0-9_]+)\s*\}", val)
    if m:
        return m.group(1), m.group(2)
    return None


def cell_is_header(td):
    return td.name == "th" or td.find(["strong", "b"]) is not None


def render_table(table, ctx, lay, indent, deferred):
    num_cols = compute_num_cols(table)
    table_w = lay.width - indent
    col_unit = table_w // num_cols
    x_base = lay.x0 + indent

    rows = get_rows(table)
    for row in rows:
        te = find_theach(row)
        cells = row_cells(row)
        if te:
            # repeating row -> jr:list with one row of cells
            render_theach_row(row, te, ctx, lay, x_base, table_w, col_unit, num_cols)
            continue
        render_static_row(row, cells, ctx, lay, x_base, table_w, col_unit, num_cols, deferred)


def column_x_widths(cells, col_unit, table_w, num_cols):
    xs = []
    widths = []
    cx = 0
    consumed = 0
    for i, c in enumerate(cells):
        span = cell_colspan(c)
        w = span * col_unit
        consumed += span
        xs.append(cx)
        widths.append(w)
        cx += w
    # stretch last cell to fill the table width
    if widths:
        widths[-1] = table_w - xs[-1]
    return xs, widths


def render_static_row(row, cells, ctx, lay, x_base, table_w, col_unit, num_cols, deferred):
    if not cells:
        return
    xs, widths = column_x_widths(cells, col_unit, table_w, num_cols)

    # estimate row height & detect special cells
    max_h = TABLE_LINE_H + 6
    cell_plans = []
    for i, td in enumerate(cells):
        w = widths[i]
        nested_tbl = td.find("table", recursive=False) or td.find("table")
        nested_ol = td.find(["ol", "ul"], recursive=False)
        loop_span = None
        for sp in td.find_all(["span", "div"], recursive=False):
            te = find_theach(sp)
            if te:
                loop_span = (sp, te)
                break
        if loop_span is None:
            te_self = None
        plan = {"td": td, "x": xs[i], "w": w, "nested_tbl": nested_tbl,
                "nested_ol": nested_ol, "loop_span": loop_span}
        cell_plans.append(plan)
        # estimate
        tlen = approx_len_of_parts(list(td.children), ctx)
        h = estimate_text_height(tlen, w - 6, TABLE_FONT, TABLE_LINE_H)
        if loop_span or nested_ol or nested_tbl:
            h = max(h, 40)
        max_h = max(max_h, h)

    # build the row as a frame
    frame_children = []
    frame_uuid = uuid()
    has_nested_table_defer = False
    for plan in cell_plans:
        td = plan["td"]; x = plan["x"]; w = plan["w"]
        header = cell_is_header(td)
        if plan["loop_span"]:
            sp, (var, listname) = plan["loop_span"]
            inner = render_loop_cell_contents(sp, var, listname, w)
            frame_children.append(cell_frame_with_xml(x, w, inner["xml"], max(max_h, inner["h"])))
        elif plan["nested_ol"] is not None and plan["nested_tbl"] is None:
            inner = render_cell_ol(td, plan["nested_ol"], w)
            frame_children.append(cell_frame_with_xml(x, w, inner["xml"], max(max_h, inner["h"])))
        elif plan["nested_tbl"] is not None:
            # render any text of the cell, defer the nested table as a sub-block
            expr = inline_expr(text_only_children(td), ctx)
            frame_children.append(cell_text_xml(x, w, expr, header, max_h))
            deferred.append(("table", plan["nested_tbl"], indent_for_defer(x_base, x)))
            has_nested_table_defer = True
        else:
            expr = inline_expr(list(td.children), ctx)
            frame_children.append(cell_text_xml(x, w, expr, header, max_h))

    frame = ('<frame><reportElement positionType="Float" x="%d" y="%d" width="%d" height="%d" uuid="%s"/>%s</frame>'
             % (x_base, lay.y, table_w, max_h, frame_uuid, "".join(frame_children)))
    lay.emit(frame, max_h)
    # deferred nested tables are emitted by caller after the table


def indent_for_defer(x_base, cell_x):
    return 0  # nested tables rendered full available width for simplicity


def text_only_children(td):
    out = []
    for c in td.children:
        if isinstance(c, Tag) and c.name in ("table",):
            continue
        out.append(c)
    return out


def cell_text_xml(x, w, expr, header, h):
    box = cell_box()
    bold = ' isBold="true"' if header else ""
    align = "Center" if header else "Left"
    return (
        '<textField isStretchWithOverflow="true" isBlankWhenNull="true" textAdjust="StretchHeight">'
        '<reportElement stretchType="ContainerHeight" x="%d" y="0" width="%d" height="%d" uuid="%s"/>'
        '%s'
        '<textElement textAlignment="%s" verticalAlignment="Top" markup="html">'
        '<font fontName="SansSerif" size="%d"%s/></textElement>'
        '<textFieldExpression><![CDATA[%s]]></textFieldExpression>'
        '</textField>'
    ) % (x, w, h, uuid(), box, align, TABLE_FONT, bold, expr)


def cell_frame_with_xml(x, w, inner_xml, h):
    # container cell: borders only, no padding so full-width children fit
    box = ('<box>'
           '<topPen lineWidth="0.75" lineColor="#000000"/>'
           '<leftPen lineWidth="0.75" lineColor="#000000"/>'
           '<bottomPen lineWidth="0.75" lineColor="#000000"/>'
           '<rightPen lineWidth="0.75" lineColor="#000000"/></box>')
    return ('<frame><reportElement stretchType="ContainerHeight" x="%d" y="0" width="%d" height="%d" uuid="%s"/>%s%s</frame>'
            % (x, w, h, uuid(), box, inner_xml))


def render_cell_ol(td, ol, w):
    sub = Layout(0, w)
    # render any leading text
    for child in td.children:
        if child is ol:
            render_list(ol, {"loopvar": None}, sub, 0)
        elif is_block(child):
            process_block(child, {"loopvar": None}, sub, 0)
        else:
            if isinstance(child, NavigableString) and not collapse_ws(str(child)):
                continue
            expr = inline_expr([child], {"loopvar": None})
            if not expr_is_empty(expr):
                text_field(sub, 0, w, expr, font=TABLE_FONT, line_h=TABLE_LINE_H, align="Left")
    return {"xml": "".join(sub.elements), "h": max(sub.y, 20)}


def render_loop_cell_contents(loop_node, var, listname, w):
    """Render a th:each loop that lives inside a table cell as an embedded jr:list."""
    cfg = LIST_CONFIG[listname]
    ctx = {"loopvar": var}
    sub = Layout(0, w)
    # render the loop body (children of the loop node) once into sub-layout
    process_children(loop_node, ctx, sub, 0)
    item_h = max(sub.y, TABLE_LINE_H + 4)
    contents = "".join(sub.elements)
    ds = ('new net.sf.jasperreports.engine.data.JRBeanCollectionDataSource('
          '$P{%s}==null?new java.util.ArrayList():$P{%s})' % (listname, listname))
    comp = (
        '<componentElement>'
        '<reportElement positionType="Float" x="0" y="0" width="%d" height="%d" uuid="%s"/>'
        '<jr:list xmlns:jr="http://jasperreports.sourceforge.net/jasperreports/components" '
        'xsi:schemaLocation="http://jasperreports.sourceforge.net/jasperreports/components '
        'http://jasperreports.sourceforge.net/xsd/components.xsd" printOrder="Vertical">'
        '<datasetRun subDataset="%s" uuid="%s">'
        '<dataSourceExpression><![CDATA[%s]]></dataSourceExpression></datasetRun>'
        '<jr:listContents height="%d" width="%d">%s</jr:listContents>'
        '</jr:list></componentElement>'
    ) % (w, item_h, uuid(), cfg["dataset"], uuid(), ds, item_h, w, contents)
    return {"xml": comp, "h": item_h}


def render_theach_row(row, te, ctx, lay, x_base, table_w, col_unit, num_cols):
    var, listname = te
    cfg = LIST_CONFIG[listname]
    loopctx = {"loopvar": var}
    cells = row_cells(row)
    xs, widths = column_x_widths(cells, col_unit, table_w, num_cols)
    row_h = TABLE_LINE_H + 6
    cell_xml = []
    for i, td in enumerate(cells):
        expr = inline_expr(list(td.children), loopctx)
        cell_xml.append(cell_text_xml(xs[i], widths[i], expr, False, row_h))
    contents = ('<frame><reportElement x="0" y="0" width="%d" height="%d" uuid="%s"/>%s</frame>'
                % (table_w, row_h, uuid(), "".join(cell_xml)))
    ds = ('new net.sf.jasperreports.engine.data.JRBeanCollectionDataSource('
          '$P{%s}==null?new java.util.ArrayList():$P{%s})' % (listname, listname))
    comp = (
        '<componentElement>'
        '<reportElement positionType="Float" x="%d" y="%d" width="%d" height="%d" uuid="%s"/>'
        '<jr:list xmlns:jr="http://jasperreports.sourceforge.net/jasperreports/components" '
        'xsi:schemaLocation="http://jasperreports.sourceforge.net/jasperreports/components '
        'http://jasperreports.sourceforge.net/xsd/components.xsd" printOrder="Vertical">'
        '<datasetRun subDataset="%s" uuid="%s">'
        '<dataSourceExpression><![CDATA[%s]]></dataSourceExpression></datasetRun>'
        '<jr:listContents height="%d" width="%d">%s</jr:listContents>'
        '</jr:list></componentElement>'
    ) % (x_base, lay.y, table_w, row_h, uuid(), cfg["dataset"], uuid(), ds,
         row_h, table_w, contents)
    lay.emit(comp, row_h)


# ----------------------------------------------------------------------------
# block dispatch
# ----------------------------------------------------------------------------
def is_block(node):
    if isinstance(node, NavigableString):
        return False
    if not isinstance(node, Tag):
        return False
    name = node.name.lower()
    if name in ("p", "div", "ol", "ul", "table", "hr", "li", "tr"):
        # a span/div with th:each is a block (loop)
        return True
    if name in INLINE_TAGS:
        if find_theach(node):
            return True
        return False
    return True


def process_block(node, ctx, lay, indent):
    if isinstance(node, NavigableString):
        txt = collapse_ws(str(node))
        if txt:
            text_field(lay, lay.x0 + indent, lay.width - indent,
                       java_str_literal(html_text_escape(txt)), text_len=len(txt))
        return
    if not isinstance(node, Tag):
        return

    name = node.name.lower()
    classes = " ".join(node.get("class") or []).lower()

    # explicit page breaks
    if "page-break-before" in classes and not node.get_text(strip=True) and not node.find(["table", "ol", "ul"]):
        emit_break(lay)
        return

    te = find_theach(node)
    if te and name not in ("tr",):
        var, listname = te
        render_top_loop(node, var, listname, ctx, lay, indent)
        return

    if name in ("ol", "ul"):
        render_list(node, ctx, lay, indent)
        return
    if name == "table":
        deferred = []
        render_table(node, ctx, lay, indent, deferred)
        for kind, dnode, dind in deferred:
            if kind == "table":
                d2 = []
                render_table(dnode, ctx, lay, indent, d2)
        # honor page break if div wrapper requested it after
        return
    if name == "hr":
        emit_hr(lay, lay.x0 + indent, lay.width - indent)
        return
    if name in ("p", "div"):
        process_children(node, ctx, lay, indent)
        if "page-break-before" in classes:
            pass
        return
    # inline-ish element used as block
    process_children(node, ctx, lay, indent)


def render_top_loop(node, var, listname, ctx, lay, indent):
    cfg = LIST_CONFIG[listname]
    loopctx = {"loopvar": var}
    w = lay.width - indent
    sub = Layout(0, w)
    process_children(node, loopctx, sub, 0)
    item_h = max(sub.y, LINE_H + 2)
    contents = "".join(sub.elements)
    ds = ('new net.sf.jasperreports.engine.data.JRBeanCollectionDataSource('
          '$P{%s}==null?new java.util.ArrayList():$P{%s})' % (listname, listname))
    comp = (
        '<componentElement>'
        '<reportElement positionType="Float" x="%d" y="%d" width="%d" height="%d" uuid="%s"/>'
        '<jr:list xmlns:jr="http://jasperreports.sourceforge.net/jasperreports/components" '
        'xsi:schemaLocation="http://jasperreports.sourceforge.net/jasperreports/components '
        'http://jasperreports.sourceforge.net/xsd/components.xsd" printOrder="Vertical">'
        '<datasetRun subDataset="%s" uuid="%s">'
        '<dataSourceExpression><![CDATA[%s]]></dataSourceExpression></datasetRun>'
        '<jr:listContents height="%d" width="%d">%s</jr:listContents>'
        '</jr:list></componentElement>'
    ) % (lay.x0 + indent, lay.y, w, item_h, uuid(), cfg["dataset"], uuid(), ds,
         item_h, w, contents)
    lay.emit(comp, item_h)


def process_children(parent, ctx, lay, indent):
    """Iterate children, grouping consecutive inline content into text blocks."""
    inline_buf = []

    def flush():
        if not inline_buf:
            return
        expr = inline_expr(inline_buf, ctx)
        tlen = approx_len_of_parts(inline_buf, ctx)
        if not expr_is_empty(expr):
            # alignment / bold heuristics from first tag
            text_field(lay, lay.x0 + indent, lay.width - indent, expr, text_len=tlen,
                       align=block_align(parent))
        inline_buf.clear()

    for child in parent.children:
        if is_block(child):
            flush()
            process_block(child, ctx, lay, indent)
        else:
            inline_buf.append(child)
    flush()


def block_align(node):
    style = (node.get("style") or "").lower()
    if "text-align:center" in style.replace(" ", "") or "text-align: center" in style:
        return "Center"
    if "text-align:right" in style.replace(" ", ""):
        return "Right"
    return "Justified"


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    with open(SRC, "r", encoding="utf-8") as f:
        raw = f.read()
    soup = BeautifulSoup(raw, "lxml")
    content = soup.find(attrs={"th:fragment": True})
    if content is None:
        content = soup.body or soup

    root = Layout(0, CONTENT_W)
    process_children(content, {"loopvar": None}, root, 0)

    # ---- chunk top-level elements into page-sized detail bands ----
    # NB: rebased positions (start_y - band_base) are authoritative because some
    # helpers advance lay.y for spacing without emitting an element.
    BAND_MAX = 740
    bands = []           # list of (list-of-xml, band_height) with y rebased
    cur = []
    band_base = None
    cur_end = 0
    for (start_y, height), xml in zip(root.meta, root.elements):
        if band_base is None:
            band_base = start_y
        rebased = start_y - band_base
        if cur and rebased + height > BAND_MAX:
            bands.append((cur, cur_end))
            cur = []
            band_base = start_y
            rebased = 0
        xml2 = xml.replace('y="%d"' % start_y, 'y="%d"' % rebased, 1)
        cur.append(xml2)
        cur_end = rebased + height
    if cur:
        bands.append((cur, cur_end))

    band_xml = ""
    for elems, end in bands:
        band_xml += ('<band height="%d" splitType="Stretch">%s</band>'
                     % (min(end + 8, 782), "".join(elems)))

    # ---- assemble subdatasets ----
    seen = set()
    subdatasets = []
    for listname, cfg in LIST_CONFIG.items():
        if cfg["dataset"] in seen:
            continue
        seen.add(cfg["dataset"])
        fields = ""
        for fld in cfg["fields"]:
            if fld == "_THIS":
                fields += ('<field name="_THIS" class="java.lang.String">'
                           '<fieldDescription><![CDATA[_THIS]]></fieldDescription></field>')
            else:
                fields += '<field name="%s" class="java.lang.String"/>' % fld
        subdatasets.append('<subDataset name="%s" uuid="%s">%s</subDataset>'
                           % (cfg["dataset"], uuid(), fields))

    # ---- assemble parameters ----
    param_xml = []
    for name in sorted(scalar_params):
        cls = "java.lang.Double" if name == "netDisbursementAmount" else "java.lang.String"
        param_xml.append('<parameter name="%s" class="%s"/>' % (name, cls))
    for listname in LIST_CONFIG:
        param_xml.append('<parameter name="%s" class="java.util.List"/>' % listname)

    header = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<jasperReport xmlns="http://jasperreports.sourceforge.net/jasperreports" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="http://jasperreports.sourceforge.net/jasperreports '
        'http://jasperreports.sourceforge.net/xsd/jasperreport.xsd" '
        'name="LoanAgreement" pageWidth="595" pageHeight="842" columnWidth="535" '
        'leftMargin="30" rightMargin="30" topMargin="30" bottomMargin="30" '
        'uuid="abcd0000-0000-0000-0000-000000000000">\n'
        '<property name="net.sf.jasperreports.default.pdf.encoding" value="Identity-H"/>\n'
        '<property name="net.sf.jasperreports.default.pdf.embedded" value="true"/>\n'
        '<property name="net.sf.jasperreports.print.keep.full.text" value="true"/>\n'
    )
    doc = (header
           + "\n".join(subdatasets) + "\n"
           + "\n".join(param_xml) + "\n"
           + '<detail>'
           + band_xml
           + '</detail>\n</jasperReport>\n')

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(doc)

    print("Wrote %s" % OUT)
    print("bands:", len(bands))
    print("elements:", len(root.elements))
    print("scalar params (%d): %s" % (len(scalar_params), ", ".join(sorted(scalar_params))))


if __name__ == "__main__":
    main()
