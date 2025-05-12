import cv2
import numpy as np
import math
import tkinter as tk
from tkinter import filedialog

# --- Global variables for mouse selection ---
drawing = False
ix, iy = -1, -1
current_x, current_y = -1, -1
staged_roi = None
confirmed_rois_list = []

# --- Animation Parameters (ADJUST THESE) ---
ANIM_AMPLITUDE = 10
ANIM_FREQUENCY = 0.025
ANIM_RIPPLE_FACTOR = 0.01 # May still need tuning

# --- Mouse callback function (SAME AS BEFORE) ---
def select_roi_callback(event, x, y, flags, param):
    global ix, iy, current_x, current_y, drawing, staged_roi
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True; ix, iy = x, y; current_x, current_y = x, y; staged_roi = None
    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing: current_x, current_y = x, y
    elif event == cv2.EVENT_LBUTTONUP:
        if drawing:
            drawing = False; x1,y1,x2,y2 = min(ix,x),min(iy,y),max(ix,x),max(iy,y)
            if x1<x2 and y1<y2: staged_roi=(x1,y1,x2,y2); print(f"Staged: {staged_roi}. 'a'-add, 'r'-reset.")
            else: staged_roi=None; print("Selection too small.")

# --- Helper Functions (SAME AS BEFORE) ---
def select_image_file():
    root = tk.Tk(); root.withdraw()
    return filedialog.askopenfilename(title="Select Character Image", filetypes=(("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")))

# --- MODIFIED ANIMATION FUNCTION ---
def animate_single_region_sway(image_to_draw_on, original_region_pixels,
                               roi_coords_for_anim, frame_count,
                               global_hair_mass_top, global_hair_mass_height): # New params
    """
    Applies sway to ONE region, considering global hair mass for amplitude.
    roi_coords_for_anim: (top, bottom, left, right) of the current ROI.
    global_hair_mass_top: The topmost Y of the entire selected hair area.
    global_hair_mass_height: The total height of the entire selected hair area.
    """
    top, bottom, left, right = roi_coords_for_anim
    roi_h = bottom - top
    roi_w = right - left

    if roi_h <= 0 or roi_w <= 0 or original_region_pixels is None or original_region_pixels.size == 0:
        return

    animated_region_slice = original_region_pixels.copy()

    for y_rel in range(roi_h): # y_rel is 0 to roi_h-1 (relative to current ROI's top)
        absolute_y_in_image = top + y_rel # Absolute Y of the current pixel row

        # *** KEY CHANGE FOR AMPLITUDE FALLOFF ***
        if global_hair_mass_height > 0:
            # Normalized position within the GLOBAL hair mass (1 at global top, 0 at global bottom)
            # We want amplitude stronger at the "tips" (top of global mass)
            normalized_y_in_global_mass = (global_hair_mass_height - (absolute_y_in_image - global_hair_mass_top)) / global_hair_mass_height
            # Clamp to avoid issues if a pixel is slightly outside the calculated global mass due to ROI selection
            normalized_y_in_global_mass = max(0.0, min(1.0, normalized_y_in_global_mass))
        else: # Fallback if global height is zero (shouldn't happen with valid ROIs)
            normalized_y_in_global_mass = 0.5 # Default to mid-amplitude

        current_amplitude = ANIM_AMPLITUDE * (normalized_y_in_global_mass ** 1.5)
        # *****************************************

        # Ripple phase is still based on absolute Y for continuity
        shift = int(current_amplitude * math.sin(ANIM_FREQUENCY * frame_count + absolute_y_in_image * ANIM_RIPPLE_FACTOR))

        if shift == 0:
            continue

        current_row_original = original_region_pixels[y_rel]
        # ... (pixel shifting logic remains the same)
        if shift > 0:
            num_pixels_to_move = roi_w - shift
            if num_pixels_to_move > 0: animated_region_slice[y_rel, shift:] = current_row_original[:-shift]
            fill_len = min(shift, roi_w); [animated_region_slice.__setitem__((y_rel, i), current_row_original[0]) for i in range(fill_len)]
        else:
            abs_shift = abs(shift)
            num_pixels_to_move = roi_w - abs_shift
            if num_pixels_to_move > 0: animated_region_slice[y_rel, :-abs_shift] = current_row_original[abs_shift:]
            fill_len = min(abs_shift, roi_w); [animated_region_slice.__setitem__((y_rel, roi_w - 1 - i), current_row_original[roi_w - 1]) for i in range(fill_len)]


    image_to_draw_on[top:bottom, left:right] = animated_region_slice


# --- Main Function ---
def main():
    global staged_roi, confirmed_rois_list, drawing, ix, iy, current_x, current_y

    image_path = select_image_file()
    if not image_path: print("No image selected."); return
    original_image = cv2.imread(image_path)
    if original_image is None: print(f"Could not read image: {image_path}"); return

    window_name = "Select Regions: Drag. 'a'-Add, 'c'-Confirm All, 'z'-Undo, 'x'-Clear All, 'q'-Quit"
    cv2.namedWindow(window_name); cv2.setMouseCallback(window_name, select_roi_callback)

    print_instructions() # Refactored instructions to a function

    final_rois_for_animation_tuples = []

    while True: # Selection loop
        display_frame = original_image.copy()
        for roi in confirmed_rois_list: cv2.rectangle(display_frame, (roi[0],roi[1]),(roi[2],roi[3]),(255,100,0),2)
        if drawing: cv2.rectangle(display_frame,(ix,iy),(current_x,current_y),(0,255,0),1)
        elif staged_roi: cv2.rectangle(display_frame,(staged_roi[0],staged_roi[1]),(staged_roi[2],staged_roi[3]),(0,255,255),2)
        cv2.imshow(window_name, display_frame); key = cv2.waitKey(10) & 0xFF

        if key == ord('a'):
            if staged_roi: confirmed_rois_list.append(staged_roi); print(f"Added: {staged_roi}. Total: {len(confirmed_rois_list)}"); staged_roi=None
            else: print("No region staged.")
        elif key == ord('r'): staged_roi=None; drawing=False; ix,iy,current_x,current_y = -1,-1,-1,-1; print("Drag reset.")
        elif key == ord('z'):
            if confirmed_rois_list: print(f"Undone: {confirmed_rois_list.pop()}. Left: {len(confirmed_rois_list)}")
            else: print("No regions to undo.")
        elif key == ord('x'): confirmed_rois_list=[]; staged_roi=None; print("All confirmed regions cleared.")
        elif key == ord('c'):
            if confirmed_rois_list:
                print(f"Confirming {len(confirmed_rois_list)} region(s).")
                final_rois_for_animation_tuples = [(r[1], r[3], r[0], r[2]) for r in confirmed_rois_list] # (top, bottom, left, right)
                break
            else: print("No regions confirmed.")
        elif key == ord('q'): print("Quitting selection."); cv2.destroyAllWindows(); return
    cv2.destroyWindow(window_name)

    if not final_rois_for_animation_tuples: print("No regions selected. Exiting."); return

    # --- Calculate global bounding box for all selected ROIs ---
    if final_rois_for_animation_tuples:
        all_tops = [r[0] for r in final_rois_for_animation_tuples]
        all_bottoms = [r[1] for r in final_rois_for_animation_tuples]
        # all_lefts = [r[2] for r in final_rois_for_animation_tuples] # Not needed for current amplitude logic
        # all_rights = [r[3] for r in final_rois_for_animation_tuples] # Not needed

        global_hair_mass_top = min(all_tops)
        global_hair_mass_bottom = max(all_bottoms)
        global_hair_mass_height = global_hair_mass_bottom - global_hair_mass_top
        if global_hair_mass_height <=0: # Should not happen if ROIs are valid
            print("Warning: Global hair mass height is zero or negative. Animation might be erratic.")
            global_hair_mass_height = 1 # Avoid division by zero
    else: # Should be caught by earlier check but defensive
        print("No ROIs for global calculation."); return
    # --- End of global bounding box calculation ---

    original_pixels_list = []
    for roi_anim_coords in final_rois_for_animation_tuples:
        top,bottom,left,right = roi_anim_coords
        if top<bottom and left<right: original_pixels_list.append(original_image[top:bottom,left:right].copy())
        else: original_pixels_list.append(None)
    if not any(p is not None for p in original_pixels_list): print("Error: All regions empty."); return

    print(f"\nStarting animation... Global Top: {global_hair_mass_top}, Global Height: {global_hair_mass_height}. Press 'q' to quit.")
    anim_frame_count = 0
    while True: # Animation loop
        current_display_frame = original_image.copy()
        for i, roi_anim_coords in enumerate(final_rois_for_animation_tuples):
            if original_pixels_list[i] is not None:
                animate_single_region_sway(current_display_frame,
                                           original_pixels_list[i],
                                           roi_anim_coords,
                                           anim_frame_count,
                                           global_hair_mass_top, # Pass global info
                                           global_hair_mass_height) # Pass global info
        cv2.imshow("Animated Character - Multi-Region Sway", current_display_frame)
        anim_frame_count += 1; key = cv2.waitKey(8) & 0xFF
        if key == ord('q'): break
    cv2.destroyAllWindows()

def print_instructions():
    print("\n--- INSTRUCTIONS ---")
    print("1. Drag mouse to draw a rectangle for an animation region.")
    print("   GREEN=dragging. YELLOW=staged after release.")
    print("2. Press 'a' to ADD the yellow staged region (it will turn BLUE).")
    print("3. Repeat 1-2 to add more regions.")
    print("4. Press 'c' to CONFIRM ALL blue regions and start animation.")
    print("5. Press 'r' to RESET/clear current yellow staged region.")
    print("6. Press 'z' to UNDO last added (blue) region.")
    print("7. Press 'x' to CLEAR ALL added (blue) regions.")
    print("8. Press 'q' to QUIT.")
    print("--------------------")

if __name__ == "__main__":
    main()