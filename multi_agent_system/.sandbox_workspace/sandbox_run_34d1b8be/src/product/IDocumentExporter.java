package product;

import model.Document;
import exception.ExportException;

public interface IDocumentExporter {
    void export(Document doc) throws ExportException;
}