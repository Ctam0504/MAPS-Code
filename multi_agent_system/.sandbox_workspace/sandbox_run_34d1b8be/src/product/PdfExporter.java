package product;

import model.Document;
import exception.ExportException;

public class PdfExporter implements IDocumentExporter {
    @Override
    public void export(Document doc) throws ExportException {
        if (doc == null || doc.getContent() == null || doc.getContent().isEmpty()) {
            throw new ExportException("Document content is empty or null");
        }
        // Implementation for exporting to PDF
        System.out.println("Exporting to PDF: " + doc.getTitle());
    }
}