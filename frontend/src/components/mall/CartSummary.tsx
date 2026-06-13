type Props = {
  totalQuantity: number;
  totalText: string;
  onCheckout: () => void;
};

export function CartSummary({ totalQuantity, totalText, onCheckout }: Props) {
  return (
    <div className="cart-summary">
      <div className="cart-summary-info">
        <span>合计</span>
        <span className="cart-summary-total">{totalText}</span>
        <span className="cart-summary-count">（{totalQuantity} 件）</span>
      </div>
      <button className="btn-primary cart-checkout-btn" onClick={onCheckout}>
        确认购买
      </button>
    </div>
  );
}
