package product;

import model.Document;
import exception.ExportException;

public class DocxExporter implements IDocumentExporter {
    @Override
    public void export(Document doc) throws ExportException {
        if (doc == null || doc.getContent() == null || doc.getContent().isEmpty()) {
            throw new ExportException("Document content cannot be empty");
        }
        // Logic to export document to DOCX format
        System.out.println("Exporting document to DOCX format: " + doc.getTitle());
    }
}