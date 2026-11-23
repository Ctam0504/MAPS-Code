import model.Document;
import exception.ExportException;
import factory.ExporterFactory;
import product.IDocumentExporter;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class TestHarness {
    @Test
    void testPdfExport() {
        Document doc = new Document("Sample Document", "This is a sample content.", "John Doe");
        ConverterService converter = new ConverterService();
        try {
            converter.convert("pdf", doc);
            assertTrue(true, "PDF export should succeed");
        } catch (ExportException e) {
            fail("PDF export should not fail: " + e.getMessage());
        }
    }

    @Test
    void testDocxExport() {
        Document doc = new Document("Sample Document", "This is a sample content.", "John Doe");
        ConverterService converter = new ConverterService();
        try {
            converter.convert("docx", doc);
            assertTrue(true, "DOCX export should succeed");
        } catch (ExportException e) {
            fail("DOCX export should not fail: " + e.getMessage());
        }
    }

    @Test
    void testEmptyContentExport() {
        Document doc = new Document("Sample Document", "", "John Doe");
        ConverterService converter = new ConverterService();
        try {
            converter.convert("pdf", doc);
            fail("Export should fail due to empty content");
        } catch (ExportException e) {
            assertEquals("Document content is empty or null", e.getMessage(), "Export exception message should match");
        }
    }

    @Test
    void testUnsupportedTypeExport() {
        Document doc = new Document("Sample Document", "This is a sample content.", "John Doe");
        ConverterService converter = new ConverterService();
        try {
            converter.convert("txt", doc);
            fail("Export should fail due to unsupported type");
        } catch (ExportException e) {
            assertEquals("Unsupported export type", e.getMessage(), "Export exception message should match");
        }
    }
}
