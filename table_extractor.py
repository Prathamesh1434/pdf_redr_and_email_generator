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
    tables from text blocks and colored rectangles. Can detect multiple
    tables on a single page based on vertical spacing.
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

        # Group words into lines based on vertical position
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

        # Group words on each line into cells based on horizontal position
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
                if abs(y_key - y_center) < 10: # Row tolerance
                    rows[y_key].append(cell)
                    found_row = True
                    break
            if not found_row:
                rows[y_center] = [cell]

        if not rows:
            all_page_tables.append(page_tables_data)
            continue

        # Identify tables based on vertical gaps between rows
        sorted_y_keys = sorted(rows.keys())

        # Calculate the bounding box for each row by taking the union of its cells
        row_bboxes = {}
        for y_key in sorted_y_keys:
            row_bbox = fitz.Rect()
            for cell in rows[y_key]:
                row_bbox |= cell['rect']
            row_bboxes[y_key] = row_bbox

        tables_on_page = []
        current_table_rows_y = []
        for i, y_key in enumerate(sorted_y_keys):
            current_table_rows_y.append(y_key)
            if i + 1 < len(sorted_y_keys):
                current_row_bbox = row_bboxes[y_key]
                next_y_key = sorted_y_keys[i+1]
                next_row_bbox = row_bboxes[next_y_key]
                vertical_gap = next_row_bbox.y0 - current_row_bbox.y1

                if vertical_gap > 20: # Threshold for table break
                    # Only consider blocks with more than one row as a table
                    if len(current_table_rows_y) > 1:
                        table_data = {"rows": []}
                        for row_y in current_table_rows_y:
                            row = sorted(rows[row_y], key=lambda c: c['rect'].x0)
                            row_cells = [{"text": c['text'], "color": c['color']} for c in row]
                            table_data["rows"].append({"cells": row_cells})
                        tables_on_page.append(table_data)
                    current_table_rows_y = []

        # Add the last table if it has more than one row
        if len(current_table_rows_y) > 1:
            table_data = {"rows": []}
            for row_y in current_table_rows_y:
                row = sorted(rows[row_y], key=lambda c: c['rect'].x0)
                row_cells = [{"text": c['text'], "color": c['color']} for c in row]
                table_data["rows"].append({"cells": row_cells})
            tables_on_page.append(table_data)

        page_tables_data["tables"] = tables_on_page
        all_page_tables.append(page_tables_data)

    return all_page_tables

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python table_extractor.py <path_to_pdf>")
        sys.exit(1)

    pdf_file = sys.argv[1]

    try:
        # Check if the file exists before processing
        with open(pdf_file, "rb"):
            pass
    except FileNotFoundError:
        print(f"Error: PDF file not found at '{pdf_file}'")
        sys.exit(1)

    try:
        extracted_data = extract_tables_from_pdf(pdf_file)

        table_counter = 1
        # Iterate through each page's data
        for page_data in extracted_data:
            # Iterate through each table found on the page
            for table in page_data['tables']:
                # Define the output filename
                output_filename = f"table_{table_counter}.json"

                # Write the table data to a JSON file
                with open(output_filename, 'w') as json_file:
                    json.dump(table, json_file, indent=4)

                print(f"Successfully saved page {page_data['page']}'s table to {output_filename}")
                table_counter += 1

    except Exception as e:
        print(f"An error occurred during table extraction or file writing: {e}")
        sys.exit(1)
