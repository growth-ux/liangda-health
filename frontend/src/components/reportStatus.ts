import type { KbDocument } from '../api/kb';

export type FactExtractStatus = KbDocument['fact_extract_status'];

export const factStatusLabel: Record<FactExtractStatus, string> = {
  pending: '等待抽取',
  processing: '抽取中',
  ready: '已抽取',
  failed: '抽取失败'
};

export const factStatusTagClass: Record<FactExtractStatus, string> = {
  pending: 'tag-warning',
  processing: 'tag-warning',
  ready: 'tag-success',
  failed: 'tag-danger'
};

export function shouldPollFactStatus(documents: Pick<KbDocument, 'fact_extract_status'>[] = []) {
  return documents.some((document) => (
    document.fact_extract_status === 'pending' || document.fact_extract_status === 'processing'
  ));
}
