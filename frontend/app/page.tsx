import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-[80vh] flex-col items-center justify-center gap-6 px-6 text-center">
      <h1 className="text-3xl font-bold sm:text-4xl">
        사장님은 장사하세요.
        <br />
        영종 AI가 나머지를 도와드립니다.
      </h1>
      <p className="max-w-xl text-base text-gray-600 sm:text-lg">
        AI 직원이 고객을 응대하고, 메뉴를 추천하고, 관광객을 연결하고, 가게의
        성과까지 알려드립니다. 근처 업체와는 AI가 서로의 손님을 자연스럽게
        연결해드려요.
      </p>
      <div className="flex flex-col gap-3 sm:flex-row">
        <Link href="/register" className="rounded-md bg-black px-6 py-3 text-white">
          우리 가게 AI 무료로 만들기
        </Link>
        <Link href="/discover" className="rounded-md border border-black px-6 py-3">
          영종도에서 뭐 할까?
        </Link>
      </div>
    </main>
  );
}
