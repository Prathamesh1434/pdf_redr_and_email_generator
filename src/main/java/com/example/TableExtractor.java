package com.example;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.rendering.PDFRenderer;
import technology.tabula.ObjectExtractor;
import technology.tabula.Page;
import technology.tabula.RectangularTextContainer;
import technology.tabula.Table;
import technology.tabula.extractors.BasicExtractionAlgorithm;

import java.awt.geom.Rectangle2D;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

public class TableExtractor {

    public static void main(String[] args) throws IOException {
        String pdfPath = "src/main/resources/sample.pdf";
        if (args.length > 0) {
            pdfPath = args[0];
        }

        List<PageTables> pageTables = new TableExtractor().extractTables(pdfPath);

        Gson gson = new GsonBuilder().setPrettyPrinting().create();
        String json = gson.toJson(pageTables);

        System.out.println(json);
    }

    // Data classes for JSON output
    public static class PageTables {
        public int page;
        public List<TableData> tables = new ArrayList<>();

        public PageTables(int page) {
            this.page = page;
        }
    }

    public static class TableData {
        public List<RowData> rows = new ArrayList<>();
    }

    public static class RowData {
        public List<CellData> cells = new ArrayList<>();
    }

    public static class CellData {
        public String text;
        public String color; // Stored as a hex string e.g. #RRGGBB

        public CellData(String text, String color) {
            this.text = text;
            this.color = color;
        }
    }

    /**
     * Extracts tables from a PDF file using Tabula for table structure
     * and PDFBox for background color analysis.
     */
    public List<PageTables> extractTables(String pdfPath) throws IOException {
        List<PageTables> allPageTables = new ArrayList<>();
        try (PDDocument document = Loader.loadPDF(new File(pdfPath))) {
            ObjectExtractor oe = new ObjectExtractor(document);
            BasicExtractionAlgorithm bea = new BasicExtractionAlgorithm();
            PDFRenderer renderer = new PDFRenderer(document);

            for (int i = 0; i < document.getNumberOfPages(); i++) {
                Page page = oe.extract(i + 1);
                PageTables pageTables = new PageTables(i + 1);

                // Render page to an image to analyze colors
                BufferedImage image = renderer.renderImage(i);

                List<Table> tables = bea.extract(page);
                for (Table table : tables) {
                    TableData tableData = new TableData();
                    for (List<RectangularTextContainer> row : table.getRows()) {
                        RowData rowData = new RowData();
                        for (RectangularTextContainer<?> cell : row) {
                            String text = cell.getText().trim();

                            // Get cell's bounding box
                            Rectangle2D.Float boundingBox = new Rectangle2D.Float(
                                    (float)cell.getLeft(),
                                    (float)cell.getTop(),
                                    (float)cell.getWidth(),
                                    (float)cell.getHeight()
                            );

                            String hexColor = getCellBackgroundColor(boundingBox, image, page);
                            rowData.cells.add(new CellData(text, hexColor));
                        }
                        if (!rowData.cells.isEmpty()) {
                            tableData.rows.add(rowData);
                        }
                    }
                    if (!tableData.rows.isEmpty()) {
                        pageTables.tables.add(tableData);
                    }
                }
                if (!pageTables.tables.isEmpty()) {
                    allPageTables.add(pageTables);
                }
            }
        }
        return allPageTables;
    }

    /**
     * Gets the background color of a cell by finding the dominant color
     * in the corresponding area of a rendered image of the page.
     * This is a simplified approach and might not be perfectly accurate for all cases.
     */
    private String getCellBackgroundColor(Rectangle2D.Float cellRect, BufferedImage pageImage, Page page) {
        // Convert PDF coordinates to image coordinates
        float x = cellRect.x;
        float y = cellRect.y;

        // Tabula gives coordinates from top-left, image is also top-left
        int imgX = (int) (x * pageImage.getWidth() / page.getWidth());
        int imgY = (int) (y * pageImage.getHeight() / page.getHeight());
        int imgWidth = (int) (cellRect.width * pageImage.getWidth() / page.getWidth());
        int imgHeight = (int) (cellRect.height * pageImage.getHeight() / page.getHeight());

        // Ensure coordinates are within image bounds
        imgX = Math.max(0, imgX);
        imgY = Math.max(0, imgY);
        imgWidth = Math.min(pageImage.getWidth() - imgX, imgWidth);
        imgHeight = Math.min(pageImage.getHeight() - imgY, imgHeight);

        if (imgWidth <= 0 || imgHeight <= 0) {
            return "#FFFFFF"; // Default white
        }

        // Find the color of the center pixel of the cell area
        int centerX = imgX + imgWidth / 2;
        int centerY = imgY + imgHeight / 2;

        int rgb = pageImage.getRGB(centerX, centerY);
        java.awt.Color color = new java.awt.Color(rgb);

        return String.format("#%02X%02X%02X", color.getRed(), color.getGreen(), color.getBlue());
    }
}
