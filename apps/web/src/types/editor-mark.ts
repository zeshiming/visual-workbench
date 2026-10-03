export type EditorMark = {
  id: string
  /** 圆心 X，相对图片宽度，0–1 */
  centerX: number
  /** 圆心 Y，相对图片高度，0–1 */
  centerY: number
  /** 半径，相对 min(宽, 高)，0–1 */
  radius: number
  description: string
}
