package Main;

import model.Document;
import exception.ExportException;
import factory.ExporterFactory;
import product.IDocumentExporter;

public class Main {
    public static void main(String[] args) {
        try {
            Document doc = new Document("Sample Document", "This is a sample content.", "John Doe");

            ConverterService converter = new ConverterService();
            converter.convert("pdf", doc);
            converter.convert("docx", doc);
        } catch (ExportException e) {
            System.err.println("Export error: " + e.getMessage());
        }
    }
}