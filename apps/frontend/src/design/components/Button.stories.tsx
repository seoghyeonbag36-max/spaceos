// Storybook 예시 — 컴포넌트 산출물 기록·공유의 단일 출처
import type { Meta, StoryObj } from "@storybook/react";
import { Button } from "./Button";

const meta: Meta<typeof Button> = { title: "Design/Button", component: Button };
export default meta;
type S = StoryObj<typeof Button>;

export const Brand: S = { args: { variant: "brand", children: "AI 추천 보기" } };
export const Naver: S = { args: { variant: "naver", children: "네이버 지도 길찾기" } };
export const Ghost: S = { args: { variant: "ghost", children: "닫기" } };
