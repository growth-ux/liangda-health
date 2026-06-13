import { Search } from 'lucide-react';
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { searchKb, type SearchResult } from '../api/kb';

export function KbSearchPanel() {
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(5);
  const searchMutation = useMutation<SearchResult[], Error>({
    mutationFn: () => searchKb(query, topK)
  });

  return (
    <section className="search-panel">
      <div className="section-title">知识库搜索</div>
      <div className="search-row">
        <div className="search-input-wrap">
          <Search size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索报告内容，例如：骨密度异常"
          />
        </div>
        <select value={topK} onChange={(event) => setTopK(Number(event.target.value))}>
          <option value={5}>Top 5</option>
          <option value={10}>Top 10</option>
        </select>
        <button className="btn-primary" onClick={() => searchMutation.mutate()} disabled={!query || searchMutation.isPending}>
          搜索
        </button>
      </div>

      {searchMutation.isError && <div className="error-box">{searchMutation.error.message}</div>}

      <div className="search-results">
        {searchMutation.data?.map((item) => (
          <article key={item.chunk_id} className="result-card">
            <div className="result-meta">
              第 {item.page_no} 页 · score {item.score.toFixed(2)}
            </div>
            <p>{item.content}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
