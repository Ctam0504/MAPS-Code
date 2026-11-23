package factory;

import product.IDocumentExporter;
import product.PdfExporter;
import product.DocxExporter;
import exception.ExportException;

public class ExporterFactory {
    public static IDocumentExporter createExporter(String type) throws ExportException {
        switch (type) {
            case "pdf":
                return new PdfExporter();
            case "docx":
                return new DocxExporter();
            default:
                throw new ExportException("Unsupported export type");
        }
    }
}