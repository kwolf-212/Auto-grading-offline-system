# pdf_calibration.py - 수정 버전

import cv2
import numpy as np
import fitz
import matplotlib.pyplot as plt
from typing import Tuple, Dict, Optional, List
import os


class PDFCalibrator:
    """PDF 간 기하학적 변환 보정 클래스"""
    
    def __init__(self, dpi: int = 150):
        self.dpi = dpi
        self.zoom = dpi / 72
        self.homography_orig_to_scan = None  # 원본 → 스캔
        self.homography_scan_to_orig = None  # 스캔 → 원본 (역행렬)
        self.orig_img = None
        self.scan_img = None
        self.params = {}
    
    def pdf_to_image(self, pdf_path: str, page_num: int = 0) -> np.ndarray:
        """PDF 페이지를 이미지로 변환"""
        doc = fitz.open(pdf_path)
        if page_num >= len(doc):
            raise ValueError(f"Page {page_num} not found")
        
        page = doc[page_num]
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n
        )
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        
        doc.close()
        return img
    
    def find_homography(self, orig_img: np.ndarray, scan_img: np.ndarray) -> Dict:
        """
        두 이미지 간 호모그래피 행렬 계산
        반환: {'orig_to_scan': H, 'scan_to_orig': H_inv}
        """
        gray_orig = cv2.cvtColor(orig_img, cv2.COLOR_BGR2GRAY)
        gray_scan = cv2.cvtColor(scan_img, cv2.COLOR_BGR2GRAY)
        
        # SIFT 특징점 검출
        detector = cv2.SIFT_create()
        kp1, des1 = detector.detectAndCompute(gray_orig, None)
        kp2, des2 = detector.detectAndCompute(gray_scan, None)
        
        if des1 is None or des2 is None:
            print("❌ 특징점을 찾을 수 없습니다.")
            return None
        
        # FLANN 매처 (더 정확함)
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        
        matches = flann.knnMatch(des1, des2, k=2)
        
        # Lowe's ratio test
        good_matches = []
        for m, n in matches:
            if m.distance < 0.75 * n.distance:
                good_matches.append(m)
        
        print(f"   발견된 매칭: {len(good_matches)}")
        
        if len(good_matches) < 10:
            print("❌ 충분한 매칭 포인트가 없습니다.")
            return None
        
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        
        # RANSAC으로 호모그래피 계산
        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        
        if H is None:
            print("❌ 호모그래피 행렬 계산 실패")
            return None
        
        # 역행렬 계산
        H_inv = np.linalg.inv(H)
        
        # 매칭 결과 시각화 (선택)
        self.matches_img = cv2.drawMatches(
            orig_img, kp1, scan_img, kp2, 
            good_matches[:50], None,
            flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS
        )
        
        return {
            'orig_to_scan': H,      # 원본 이미지를 스캔 이미지 좌표계로
            'scan_to_orig': H_inv,  # 스캔 이미지를 원본 좌표계로
            'matches': len(good_matches)
        }
    
    def calibrate_from_pdfs(
        self,
        original_pdf_path: str,
        scan_pdf_path: str,
        page_num: int = 0
    ) -> Dict[str, float]:
        """두 PDF를 직접 비교하여 보정 계수 계산"""
        print(f"\n🔧 PDF Calibration - Page {page_num + 1}")
        print("=" * 50)
        
        self.orig_img = self.pdf_to_image(original_pdf_path, page_num)
        self.scan_img = self.pdf_to_image(scan_pdf_path, page_num)
        
        print(f"   원본 크기: {self.orig_img.shape[1]}x{self.orig_img.shape[0]}")
        print(f"   스캔 크기: {self.scan_img.shape[1]}x{self.scan_img.shape[0]}")
        
        result = self.find_homography(self.orig_img, self.scan_img)
        
        if result is None:
            print("❌ 보정 실패")
            return {}
        
        self.homography_orig_to_scan = result['orig_to_scan']
        self.homography_scan_to_orig = result['scan_to_orig']
        
        # 변환 계수 추출 (스캔 → 원본 기준)
        H = self.homography_scan_to_orig
        
        scale_x = np.sqrt(H[0, 0]**2 + H[1, 0]**2)
        scale_y = np.sqrt(H[0, 1]**2 + H[1, 1]**2)
        rotation = np.arctan2(H[1, 0], H[0, 0])
        translate_x = H[0, 2]
        translate_y = H[1, 2]
        
        self.params = {
            'scale_x': scale_x,
            'scale_y': scale_y,
            'rotation_deg': rotation * 180 / np.pi,
            'translate_x': translate_x,
            'translate_y': translate_y,
            'homography_scan_to_orig': H.tolist(),
            'homography_orig_to_scan': self.homography_orig_to_scan.tolist(),
            'matches': result['matches']
        }
        
        print("\n📊 Calibration Parameters (Scan → Original transformation):")
        print(f"   Scale X: {self.params['scale_x']:.6f}")
        print(f"   Scale Y: {self.params['scale_y']:.6f}")
        print(f"   Rotation: {self.params['rotation_deg']:.4f}°")
        print(f"   Translate X: {self.params['translate_x']:.2f} px")
        print(f"   Translate Y: {self.params['translate_y']:.2f} px")
        
        return self.params
    
    def transform_scan_to_match_original(self) -> np.ndarray:
        """스캔 이미지를 변환하여 원본 이미지와 일치하도록 함"""
        if self.homography_scan_to_orig is None:
            print("❌ 먼저 calibrate_from_pdfs()를 실행하세요.")
            return None
        
        h, w = self.orig_img.shape[:2]
        transformed = cv2.warpPerspective(
            self.scan_img, 
            self.homography_scan_to_orig,  # 스캔 → 원본 변환
            (w, h)
        )
        return transformed
    
    def transform_original_to_scan(self) -> np.ndarray:
        """원본 이미지를 스캔 좌표계로 변환 (검증용)"""
        if self.homography_orig_to_scan is None:
            print("❌ 먼저 calibrate_from_pdfs()를 실행하세요.")
            return None
        
        h, w = self.scan_img.shape[:2]
        transformed = cv2.warpPerspective(
            self.orig_img, 
            self.homography_orig_to_scan,  # 원본 → 스캔 변환
            (w, h)
        )
        return transformed
    
    def verify_calibration(self) -> Dict:
        """보정 검증: 변환 후 원본과 스캔본의 주요 지점 비교"""
        transformed = self.transform_scan_to_match_original()
        if transformed is None:
            return {}
        
        # 크기 통일
        h, w = self.orig_img.shape[:2]
        if transformed.shape[:2] != (h, w):
            transformed = cv2.resize(transformed, (w, h))
        
        # MSE, PSNR 계산
        mse = np.mean((self.orig_img.astype(float) - transformed.astype(float)) ** 2)
        psnr = 20 * np.log10(255.0 / np.sqrt(mse)) if mse > 0 else 100
        
        # SSIM 계산
        gray1 = cv2.cvtColor(self.orig_img, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(transformed, cv2.COLOR_BGR2GRAY)
        ssim = self._ssim(gray1, gray2)
        
        return {'mse': mse, 'psnr': psnr, 'ssim': ssim}
    
    def _ssim(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """SSIM 계산"""
        C1 = (0.01 * 255) ** 2
        C2 = (0.03 * 255) ** 2
        
        img1 = img1.astype(np.float64)
        img2 = img2.astype(np.float64)
        
        mu1 = cv2.GaussianBlur(img1, (11, 11), 1.5)
        mu2 = cv2.GaussianBlur(img2, (11, 11), 1.5)
        
        mu1_sq = mu1 ** 2
        mu2_sq = mu2 ** 2
        mu1_mu2 = mu1 * mu2
        
        sigma1_sq = cv2.GaussianBlur(img1 ** 2, (11, 11), 1.5) - mu1_sq
        sigma2_sq = cv2.GaussianBlur(img2 ** 2, (11, 11), 1.5) - mu2_sq
        sigma12 = cv2.GaussianBlur(img1 * img2, (11, 11), 1.5) - mu1_mu2
        
        ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / ((mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))
        
        return float(np.mean(ssim_map))
    
    def show_verification(self):
        """보정 검증 결과 표시"""
        transformed = self.transform_scan_to_match_original()
        if transformed is None:
            return
        
        h, w = self.orig_img.shape[:2]
        if transformed.shape[:2] != (h, w):
            transformed = cv2.resize(transformed, (w, h))
        
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        
        # 1. Original
        axes[0, 0].imshow(cv2.cvtColor(self.orig_img, cv2.COLOR_BGR2RGB))
        axes[0, 0].set_title("1. ORIGINAL (Target)", fontsize=12, fontweight='bold')
        axes[0, 0].axis('off')
        
        # 2. Scanned (Before)
        axes[0, 1].imshow(cv2.cvtColor(self.scan_img, cv2.COLOR_BGR2RGB))
        axes[0, 1].set_title(f"2. SCANNED (Before)\n{self.scan_img.shape[1]}x{self.scan_img.shape[0]}", fontsize=12)
        axes[0, 1].axis('off')
        
        # 3. Transformed (After) - KEY RESULT
        axes[0, 2].imshow(cv2.cvtColor(transformed, cv2.COLOR_BGR2RGB))
        axes[0, 2].set_title(f"3. TRANSFORMED (After Calibration)\n{w}x{h}", fontsize=12, fontweight='bold')
        axes[0, 2].axis('off')
        
        # 4. Difference Map
        diff = cv2.absdiff(self.orig_img, transformed)
        diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        axes[1, 0].imshow(diff_gray, cmap='hot')
        axes[1, 0].set_title(f"4. Difference Map\nMean: {diff_gray.mean():.1f}", fontsize=12)
        axes[1, 0].axis('off')
        
        # 5. Overlay
        overlay = cv2.addWeighted(self.orig_img, 0.5, transformed, 0.5, 0)
        axes[1, 1].imshow(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
        axes[1, 1].set_title("5. Overlay (Original + Transformed)", fontsize=12)
        axes[1, 1].axis('off')
        
        # 6. Feature matches
        if hasattr(self, 'matches_img'):
            axes[1, 2].imshow(cv2.cvtColor(self.matches_img, cv2.COLOR_BGR2RGB))
            axes[1, 2].set_title(f"6. Feature Matches ({self.params.get('matches', 0)} points)", fontsize=12)
        else:
            axes[1, 2].axis('off')
            axes[1, 2].set_title("6. Feature Matches", fontsize=12)
        axes[1, 2].axis('off')
        
        plt.suptitle("CALIBRATION VERIFICATION: Scan → Original Transformation", fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.show()
        
        # 검증 결과 출력
        verify = self.verify_calibration()
        print("\n" + "=" * 60)
        print("📊 VERIFICATION RESULTS")
        print("=" * 60)
        print(f"   MSE:  {verify['mse']:.2f} (0 = perfect)")
        print(f"   PSNR: {verify['psnr']:.2f} dB (>30 = good)")
        print(f"   SSIM: {verify['ssim']:.4f} (1 = perfect)")
        
        if verify['psnr'] >= 30:
            print("\n   ✅ Calibration successful! Transformed scan matches original.")
        else:
            print("\n   ⚠️ Calibration may need improvement. Check feature matches.")
    
    def save_transformed_scan(self, output_path: str = "transformed_scan.png"):
        """변환된 스캔본 저장"""
        transformed = self.transform_scan_to_match_original()
        if transformed is not None:
            cv2.imwrite(output_path, transformed)
            print(f"\n📸 Transformed scan saved: {output_path}")
            print(f"   Size: {transformed.shape[1]}x{transformed.shape[0]}")
    
    def save_feature_matches(self, output_path: str = "feature_matches.png"):
        """특징점 매칭 결과 저장"""
        if hasattr(self, 'matches_img'):
            cv2.imwrite(output_path, self.matches_img)
            print(f"📸 Feature matches saved: {output_path}")
    
    def print_transformation_formula(self):
        """변환 공식 출력"""
        if not self.params:
            print("❌ No calibration parameters. Run calibrate_from_pdfs() first.")
            return
        
        print("\n" + "=" * 60)
        print("📐 TRANSFORMATION FORMULA (Scan → Original)")
        print("=" * 60)
        print("""
        Apply to any coordinate (x, y) from the SCANNED PDF:
        
            x_original = x * {sx:.6f} + {tx:.2f}
            y_original = y * {sy:.6f} + {ty:.2f}
        
        Full Homography Matrix H (Scan → Original):
        
            [ x' ]   [ {h00:.4f}  {h01:.4f}  {h02:.2f} ] [ x ]
            [ y' ] = [ {h10:.4f}  {h11:.4f}  {h12:.2f} ] [ y ]
            [ 1  ]   [ {h20:.4f}  {h21:.4f}  {h22:.4f} ] [ 1 ]
        """.format(
            sx=self.params['scale_x'],
            sy=self.params['scale_y'],
            tx=self.params['translate_x'],
            ty=self.params['translate_y'],
            h00=self.params['homography_scan_to_orig'][0][0],
            h01=self.params['homography_scan_to_orig'][0][1],
            h02=self.params['homography_scan_to_orig'][0][2],
            h10=self.params['homography_scan_to_orig'][1][0],
            h11=self.params['homography_scan_to_orig'][1][1],
            h12=self.params['homography_scan_to_orig'][1][2],
            h20=self.params['homography_scan_to_orig'][2][0],
            h21=self.params['homography_scan_to_orig'][2][1],
            h22=self.params['homography_scan_to_orig'][2][2]
        ))


def main():
    original_pdf = "3.pdf"                     # 원본 답지
    scan_pdf = "20260512112241347_0001.pdf"    # 스캔된 답안지
    
    if not os.path.exists(original_pdf):
        print(f"❌ File not found: {original_pdf}")
        return
    
    if not os.path.exists(scan_pdf):
        print(f"❌ File not found: {scan_pdf}")
        return
    
    calibrator = PDFCalibrator(dpi=150)
    params = calibrator.calibrate_from_pdfs(original_pdf, scan_pdf, page_num=0)
    
    if not params:
        print("❌ Calibration failed")
        return
    
    calibrator.print_transformation_formula()
    calibrator.save_transformed_scan("transformed_scan.png")
    calibrator.save_feature_matches("feature_matches.png")
    calibrator.show_verification()


if __name__ == "__main__":
    main()