package service;

import model.Document;
import exception.ExportException;
import factory.ExporterFactory;
import product.IDocumentExporter;

public class ConverterService {
    public void convert(String type, Document doc) throws ExportException {
        if (doc.getContent() == null || doc.getContent().isEmpty()) {
            throw new ExportException("Document content is empty");
        }
        IDocumentExporter exporter = ExporterFactory.createExporter(type);
        exporter.export(doc);
    }
}