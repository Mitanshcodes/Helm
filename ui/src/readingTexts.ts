// OWNER: P4
// Paragraphs for the "read this aloud" step, which teaches Helm what talking looks like so speech does not fire
// gestures. Plain words and short sentences, so anyone can read them at their own pace. These must stay
// different from the text P3 uses for the false-trigger evaluation, or that number would be inflated.

export const READING_TEXTS: string[] = [
  "The morning market opens before the sun is fully up. Farmers stack crates of apples, pears and late tomatoes, " +
    "and someone always brings warm bread wrapped in a towel. By eight o'clock the street is loud with people " +
    "asking prices, trading recipes and arguing about the weather. A small dog sleeps under the flower stall, " +
    "and nobody has the heart to move it. When the bell rings at noon, the tables fold away and the street is quiet again.",
  "Our neighbor built a boat in his garage over three winters. He measured every plank twice and sanded each one " +
    "by hand. When spring came, half the block helped carry it down to the lake. It floated on the first try, which " +
    "surprised everyone except him. He named it after his grandmother and painted the letters in bright yellow. " +
    "Now on calm evenings you can see him rowing slowly past the old pier.",
  "The library on the corner has a reading room with tall windows and green lamps. On rainy days it fills up with " +
    "students, retired teachers and people who simply want somewhere dry to sit. The librarian knows almost everyone " +
    "by name and remembers what they like to read. Last week she found a letter tucked inside a novel from 1962. " +
    "It was a recipe for lemon cake, written in careful blue ink.",
  "Every summer the town holds a kite festival on the hill behind the school. Families arrive early to claim a spot " +
    "and untangle their strings. The best kites are homemade, built from sticks, paper and a lot of patience. When the " +
    "wind is right, the sky fills with dragons, fish and long ribbon tails. At sunset everyone sits on the grass, " +
    "and the last kites drift down like falling leaves.",
];

export function pickText(seed: number): string {
  return READING_TEXTS[Math.abs(seed) % READING_TEXTS.length];
}
