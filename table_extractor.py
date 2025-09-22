import fitz  # PyMuPDF
import json
import sys

def find_cell_color(rect, drawings):
    """
    Finds the background color of a cell by checking for a drawing that contains it.
    """
    cell_center = fitz.Point((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2)
    for drawing in drawings:
        if drawing['type'] == 'f' and 'rect' in drawing:
            if drawing['rect'].contains(cell_center):
                if 'fill' in drawing and drawing['fill'] is not None:
                    color = drawing['fill']
                    return f"#{int(color[0] * 255):02X}{int(color[1] * 255):02X}{int(color[2] * 255):02X}"
    return "#FFFFFF"

def extract_tables_from_pdf(pdf_path):
    """
    Extracts tables from a PDF using PyMuPDF by manually reconstructing
    tables from text blocks and colored rectangles.
    """
    doc = fitz.open(pdf_path)
    all_page_tables = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        page_tables_data = {"page": page_num + 1, "tables": []}

        drawings = page.get_drawings()
        words = page.get_text("words")

        if not words:
            continue

        # Group words into lines
        words.sort(key=lambda w: (w[1], w[0]))
        lines = {}
        for w in words:
            y0 = w[1]
            found_line = False
            for y_key in lines.keys():
                if abs(y_key - y0) < 5:
                    lines[y_key].append(w)
                    found_line = True
                    break
            if not found_line:
                lines[y0] = [w]

        # Group words on each line into cells
        cells = []
        for y_key in sorted(lines.keys()):
            line_words = sorted(lines[y_key], key=lambda w: w[0])
            if not line_words: continue

            current_cell_text = [line_words[0][4]]
            current_cell_bbox = fitz.Rect(line_words[0][:4])

            for i in range(1, len(line_words)):
                prev_word_bbox = fitz.Rect(line_words[i-1][:4])
                current_word_bbox = fitz.Rect(line_words[i][:4])

                if abs(current_word_bbox.x0 - prev_word_bbox.x1) < 5:
                    current_cell_text.append(line_words[i][4])
                    current_cell_bbox.include_rect(current_word_bbox)
                else:
                    cells.append({'rect': current_cell_bbox, 'text': " ".join(current_cell_text)})
                    current_cell_text = [line_words[i][4]]
                    current_cell_bbox = current_word_bbox
            cells.append({'rect': current_cell_bbox, 'text': " ".join(current_cell_text)})

        # Assign colors to the merged cells
        for cell in cells:
            cell['color'] = find_cell_color(cell['rect'], drawings)

        # Group cells into rows
        rows = {}
        for cell in cells:
            y_center = (cell['rect'].y0 + cell['rect'].y1) / 2
            found_row = False
            for y_key in rows.keys():
                if abs(y_key - y_center) < 10:
                    rows[y_key].append(cell)
                    found_row = True
                    break
            if not found_row:
                rows[y_center] = [cell]

        table_data = {"rows": []}
        for y_key in sorted(rows.keys()):
            row = rows[y_key]
            row.sort(key=lambda c: c['rect'].x0)
            row_cells = [{"text": c['text'], "color": c['color']} for c in row]
            table_data["rows"].append({"cells": row_cells})

        page_tables_data["tables"].append(table_data)
        all_page_tables.append(page_tables_data)

    return all_page_tables

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python table_extractor.py <path_to_pdf>")
        sys.exit(1)

    pdf_file = sys.argv[1]

    try:
        with open(pdf_file, "rb"):
            pass
    except FileNotFoundError:
        print(f"Error: '{pdf_file}' not found.")
        sys.exit(1)

    try:
        extracted_data = extract_tables_from_pdf(pdf_file)
        print(json.dumps(extracted_data, indent=2))
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
