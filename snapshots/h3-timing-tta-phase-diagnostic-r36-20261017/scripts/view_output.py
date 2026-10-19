"""Inverse coordinates, retain all raw detections; never choose a new person."""
import copy
from math_core import inverse_points,inverse_box,iou

def inverse_pose(raw,identity,view):
    result=copy.deepcopy(raw)
    for row,anchor in zip(result['frames'],identity['frames']):
        for person in row['persons']:
            person['r36_view_coordinates']=copy.deepcopy(person['coco17_xy'])
            person['r36_view_scores']=copy.deepcopy(person['coco17_score'])
            person['r36_view_box']=copy.deepcopy(person['box_xyxy'])
            xy,sc,rs,inside=inverse_points(person['coco17_xy'],person['coco17_score'],view,1312,736)
            person['coco17_xy']=xy.tolist();person['coco17_score']=sc.tolist()
            person['r36_inverse_raw_scores']=rs.tolist();person['r36_original_canvas_valid']=inside.tolist()
            person['box_xyxy']=inverse_box(person['box_xyxy'],view,1312).tolist()
        i,j=row['selected_person'],anchor['selected_person']
        selected_iou=None if i is None or j is None else iou(row['persons'][i]['box_xyxy'],anchor['persons'][j]['box_xyxy'])
        okay=selected_iou is not None and selected_iou>=.5 and not row['selection_ambiguous'] and not anchor['selection_ambiguous']
        row['r36_identity_correspondence']={'valid':okay,'selected_inverse_box_iou':selected_iou,'threshold':.5,'selected_person_unchanged':True}
        if i is not None and not okay:
            row['persons'][i]['coco17_score']=[0.]*17
    result['r36_coordinate_space']='original1312x736; raw transformed detections retained'
    result['r36_view']=view
    return result
