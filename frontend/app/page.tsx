import Link from "next/link";

export default function Home() {
  return (
    <main className="relative overflow-hidden bg-cream">
      <div
        className="pointer-events-none absolute left-1/2 top-[-140px] h-[420px] w-[640px] -translate-x-1/2 rounded-full sm:h-[560px] sm:w-[900px]"
        style={{
          background:
            "radial-gradient(circle, rgba(217,113,60,0.14) 0%, rgba(217,113,60,0) 70%)",
        }}
      />

      <div className="relative z-10 flex min-h-[80vh] flex-col items-center justify-center gap-6 px-6 pb-24 pt-10 text-center sm:gap-7 sm:px-10">
        <span className="rounded-full bg-coral/10 px-4 py-1.5 text-xs font-medium text-coral-dark sm:text-sm">
          영종도 로컬 AI
        </span>
        <h1 className="max-w-sm break-keep font-display text-[30px] font-normal leading-[1.5] text-coral-dark sm:max-w-4xl sm:text-[50px] sm:leading-[1.42]">
          사장님은 장사하세요.
          <br />
          영종 AI가 나머지를 도와드립니다.
        </h1>
        <p className="max-w-xs break-keep text-[14.5px] leading-[1.85] text-ink-muted sm:max-w-xl sm:text-[17px] sm:leading-[1.9]">
          AI 직원이 고객을 응대하고, 메뉴를 추천하고, 관광객을 연결하고, 가게의
          성과까지 알려드립니다.
          <br className="hidden sm:block" />
          근처 업체와는 AI가 서로의 손님을 자연스럽게 연결해드려요.
        </p>
        <div className="mt-2 flex w-full max-w-xs flex-col gap-3 sm:w-auto sm:max-w-none sm:flex-row sm:gap-4">
          <Link
            href="/register"
            className="rounded-full bg-coral px-8 py-4 text-[15px] font-medium text-white shadow-[0_10px_24px_rgba(217,113,60,0.3)] sm:text-[15.5px]"
          >
            우리 가게 AI 무료로 만들기
          </Link>
          <Link
            href="/discover"
            className="rounded-full border-[1.5px] border-coral-dark bg-white/40 px-8 py-4 text-[15px] font-medium text-coral-dark sm:text-[15.5px]"
          >
            영종도에서 뭐 할까?
          </Link>
        </div>
      </div>

      <svg
        viewBox="0 0 1440 240"
        preserveAspectRatio="none"
        className="pointer-events-none absolute bottom-0 left-0 z-0 h-[140px] w-full sm:h-[240px]"
      >
        <circle cx="1180" cy="60" r="46" fill="#f4c98a" opacity="0.55" />
        <path
          d="M0,64 C56,48 90,44 128,58 M180,50 C216,36 250,32 288,46"
          stroke="#8a97a3"
          strokeWidth="3"
          strokeLinecap="round"
          fill="none"
          opacity="0.5"
        />
        <path
          d="M0,130 C260,190 460,60 760,110 C980,148 1180,60 1440,120 L1440,240 L0,240 Z"
          fill="#7fb3c4"
          opacity="0.3"
        />
        <path
          d="M0,170 C300,110 560,220 860,150 C1080,100 1260,190 1440,150 L1440,240 L0,240 Z"
          fill="#d9713c"
          opacity="0.22"
        />
        <path
          d="M0,205 C320,165 540,235 840,190 C1060,155 1260,215 1440,195 L1440,240 L0,240 Z"
          fill="#b85a2a"
          opacity="0.85"
        />
      </svg>
    </main>
  );
}
