export interface MasterQuote {
  id: number;
  name: string;
  quote: string;
  likes: number;
}

export const FALLBACK_QUOTES: MasterQuote[] = [
  { id: 1, name: "워런 버핏", quote: "주식 시장은 인내심 없는 사람의 돈을 인내심 있는 사람에게 전달하는 곳이다.", likes: 0 },
  { id: 2, name: "워런 버핏", quote: "훌륭한 기업을 공정한 가격에 사는 것이 공정한 기업을 훌륭한 가격에 사는 것보다 훨씬 낫다.", likes: 0 },
  { id: 3, name: "워런 버핏", quote: "리스크는 자신이 무엇을 하는지 모를 때 생긴다.", likes: 0 },
  { id: 4, name: "워런 버핏", quote: "남들이 탐욕스러울 때 두려워하고, 남들이 두려워할 때 탐욕스러워져라.", likes: 0 },
  { id: 5, name: "워런 버핏", quote: "우리가 선호하는 보유 기간은 영원히다.", likes: 0 },
  { id: 6, name: "찰리 멍거", quote: "모든 지혜는 역설에서 시작된다.", likes: 0 },
  { id: 7, name: "찰리 멍거", quote: "성공하고 싶다면, 스스로를 죽이고 싶지 않은 곳에서 일하라.", likes: 0 },
  { id: 8, name: "찰리 멍거", quote: "훌륭한 기업의 주식을 사서 앉아있어라.", likes: 0 },
  { id: 9, name: "찰리 멍거", quote: "아이디어를 뒤집어라. 항상 뒤집어라.", likes: 0 },
  { id: 10, name: "찰리 멍거", quote: "인내는 무기이고, 복리는 마법이다.", likes: 0 },
  { id: 11, name: "조지 소로스", quote: "주식 시장에서 성공하는 것은 예측하는 것이 아니라 반응하는 것이다.", likes: 0 },
  { id: 12, name: "조지 소로스", quote: "나는 틀릴 수 있다. 중요한 것은 내가 틀렸을 때 얼마나 잃느냐다.", likes: 0 },
  { id: 13, name: "조지 소로스", quote: "시장은 항상 어떤 방향으로 편향되어 있다. 완전히 균형 잡힌 시장이란 없다.", likes: 0 },
  { id: 14, name: "피터 린치", quote: "주식을 사기 전에 집을 사는 것처럼 조사하라.", likes: 0 },
  { id: 15, name: "피터 린치", quote: "당신이 이해하지 못하는 회사에 투자하지 마라.", likes: 0 },
  { id: 16, name: "피터 린치", quote: "장기적으로 주식은 채권보다 더 나은 수익을 낸다.", likes: 0 },
  { id: 17, name: "피터 린치", quote: "열 개 종목 중 여섯이 맞으면 월스트리트에서 뛰어난 성과를 낸 것이다.", likes: 0 },
];
