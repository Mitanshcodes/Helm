// OWNER: P4
// MediaPipe Face Mesh landmark indices for the contours the camera card draws over the preview.

export const N_LANDMARKS = 478;

export const FACE_OVAL = [
  10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
  172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
];
export const LIPS = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185];
export const EYE_A = [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466];
export const EYE_B = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246];
export const BROW_A = [276, 283, 282, 295, 285];
export const BROW_B = [46, 53, 52, 65, 55];

export const NOSE = [168, 6, 197, 195, 5, 4];

export const CLOSED_CONTOURS = [FACE_OVAL, LIPS, EYE_A, EYE_B];
export const OPEN_CONTOURS = [BROW_A, BROW_B, NOSE];
