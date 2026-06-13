import type { KbDocument } from '../api/kb';
import { ReportCard } from './ReportCard';

type Props = {
  documents: KbDocument[];
  deletingDocumentId: string | null;
  onDelete: (documentId: string) => void;
  onUploadClick: () => void;
};

export function ReportGrid({ documents, deletingDocumentId, onDelete, onUploadClick }: Props) {
  return (
    <div className="reports-grid">
      <ReportCard isNew onUploadClick={onUploadClick} />
      {documents.map((document) => (
        <ReportCard
          key={document.document_id}
          document={document}
          deleting={deletingDocumentId === document.document_id}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}
