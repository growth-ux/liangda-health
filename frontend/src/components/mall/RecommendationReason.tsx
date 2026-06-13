type Props = {
  reason: string;
};

export function RecommendationReason({ reason }: Props) {
  return (
    <div className="product-recommend-box">
      <div className="product-recommend-title">💡 为什么推荐这件商品？</div>
      <div className="product-recommend-text">{reason}</div>
    </div>
  );
}
