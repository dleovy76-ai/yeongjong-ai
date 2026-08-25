// Home 대시보드와 Performance 화면이 같은 시각 언어를 쓰도록 공유하는
// Funnel 컴포넌트 - 두 화면이 서로 다른 서비스처럼 보이지 않게 한다.

export function FunnelNode({
  icon,
  title,
  period,
  value,
  caption,
  isZero,
  emptyNote,
}: {
  icon: string;
  title: string;
  period?: string;
  value?: string;
  caption?: string;
  isZero?: boolean;
  emptyNote?: string;
}) {
  return (
    <div className="flex flex-1 flex-col items-center rounded-lg border border-gray-200 bg-white p-4 text-center">
      <span className="text-2xl">{icon}</span>
      <p className="mt-1 text-sm font-semibold">{title}</p>
      {period && <p className="text-sm text-gray-500">{period}</p>}
      {value !== undefined && <p className="mt-1 text-xl font-bold tabular-nums">{value}</p>}
      {caption && <p className="mt-1 text-sm text-gray-600">{caption}</p>}
      {isZero && emptyNote && <p className="mt-1 text-sm text-gray-600">{emptyNote}</p>}
    </div>
  );
}

export function FunnelArrow() {
  return (
    <div className="flex items-center justify-center text-gray-300">
      <span className="sm:hidden">↓</span>
      <span className="hidden sm:inline">→</span>
    </div>
  );
}
