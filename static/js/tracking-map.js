var trackingMap = null;
var geofenceMap = null;
var heatmapMap = null;
var employeeMarkers = {};
var zoneLayers = {};
var currentDrawLayer = null;
var drawMode = 'view';
var drawnItems = [];
var mapTileLayer = null;
var autoCenter = true;
var mapMarkerIcon = null;

function createMapIcon(color, label) {
  var size = label ? 36 : 28;
  var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="' + color + '" stroke="#fff" stroke-width="1.5"><circle cx="12" cy="12" r="10"/></svg>';
  var iconUrl = 'data:image/svg+xml;base64,' + btoa(svg);
  return L.icon({
    iconUrl: iconUrl,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2]
  });
}

function createEmployeeIcon(active) {
  var color = active ? '#22c55e' : '#566580';
  var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">' +
    '<circle cx="16" cy="16" r="14" fill="' + color + '" stroke="#fff" stroke-width="2"/>' +
    '<circle cx="16" cy="12" r="5" fill="#fff" opacity="0.9"/>' +
    '<path d="M8 26c0-4.418 3.582-8 8-8s8 3.582 8 8" fill="#fff" opacity="0.9"/>' +
    '</svg>';
  return L.icon({
    iconUrl: 'data:image/svg+xml;base64,' + btoa(svg),
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -16]
  });
}

function getDarkTileLayer() {
  return L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; CARTO',
    subdomains: 'abcd',
    maxZoom: 19,
    minZoom: 3
  });
}

function initTrackingMap(data) {
  if (document.getElementById('trackingMap')) {
    trackingMap = L.map('trackingMap', {
      center: [data.bloodBankLat || 32.0755, data.bloodBankLng || 23.9752],
      zoom: 15,
      zoomControl: false,
      attributionControl: false
    });
    L.control.zoom({ position: 'bottomleft' }).addTo(trackingMap);
    getDarkTileLayer().addTo(trackingMap);
    if (data.zones) {
      data.zones.forEach(function(z) { addZoneToMap(trackingMap, z); });
    }
    trackingMap.on('moveend', function() {
      if (autoCenter) {
        document.getElementById('autoCenterBtn').classList.remove('active');
      }
    });
  }
}

function initGeofenceMap(data) {
  if (document.getElementById('geofenceMap')) {
    geofenceMap = L.map('geofenceMap', {
      center: [data.bloodBankLat || 32.0755, data.bloodBankLng || 23.9752],
      zoom: 15,
      zoomControl: false,
      attributionControl: false
    });
    L.control.zoom({ position: 'bottomleft' }).addTo(geofenceMap);
    getDarkTileLayer().addTo(geofenceMap);
    if (data.zones) {
      data.zones.forEach(function(z) { addZoneToMap(geofenceMap, z); });
    }
    geofenceMap.on('click', function(e) {
      if (drawMode === 'circle') {
        handleCircleDraw(e.latlng);
      } else if (drawMode === 'polygon') {
        handlePolygonDraw(e.latlng);
      } else if (drawMode === 'rectangle') {
        handleRectangleDraw(e.latlng);
      }
    });
  }
}

function initHeatmapMap(data) {
  if (document.getElementById('heatmapMap') && !heatmapMap) {
    heatmapMap = L.map('heatmapMap', {
      center: [data.bloodBankLat || 32.0755, data.bloodBankLng || 23.9752],
      zoom: 14,
      zoomControl: false,
      attributionControl: false
    });
    L.control.zoom({ position: 'bottomleft' }).addTo(heatmapMap);
    getDarkTileLayer().addTo(heatmapMap);
  }
}

function addZoneToMap(map, z) {
  var color = z.color || '#22c55e';
  var opacity = z.is_restricted ? 0.6 : 0.3;
  var layer = null;
  if (z.zone_type === 'circle' && z.center_lat && z.center_lng) {
    layer = L.circle([z.center_lat, z.center_lng], {
      radius: z.radius || 200,
      color: color,
      fillColor: color,
      fillOpacity: opacity,
      weight: 2,
      opacity: 0.8
    }).addTo(map);
    if (z.is_restricted) {
      L.marker([z.center_lat, z.center_lng], {
        icon: L.divIcon({
          className: 'restricted-marker',
          html: '<i class="ti ti-shield-lock" style="color:#ef4444;font-size:20px"></i>',
          iconSize: [20, 20],
          iconAnchor: [10, 10]
        })
      }).addTo(map);
    }
  } else if (z.zone_type === 'polygon' || z.zone_type === 'rectangle') {
    var coords = (typeof z.coordinates === 'string') ? JSON.parse(z.coordinates) : (z.coordinates || []);
    if (coords.length >= 3) {
      var latlngs = coords.map(function(c) { return [c.lat, c.lng]; });
      layer = L.polygon(latlngs, {
        color: color,
        fillColor: color,
        fillOpacity: opacity,
        weight: 2,
        opacity: 0.8
      }).addTo(map);
    }
  }
  if (layer) {
    var bound = function(l, zid) {
      l.bindPopup(
        '<div style="font-family:Cairo,sans-serif;min-width:200px">' +
        '<div style="font-weight:700;font-size:14px;margin-bottom:4px">' + z.name + '</div>' +
        '<div style="font-size:12px;color:#8899b4">' +
        '<div>النوع: ' + z.zone_type + '</div>' +
        (z.radius ? '<div>نصف القطر: ' + z.radius + 'م</div>' : '') +
        (z.address ? '<div>العنوان: ' + z.address + '</div>' : '') +
        '<div>الحالة: ' + (z.is_active ? 'نشط' : 'غير نشط') + '</div>' +
        (z.is_restricted ? '<div style="color:#ef4444">🚫 منطقة محظورة</div>' : '') +
        '</div></div>'
      );
    };
    bound(layer, z.id);
    zoneLayers[z.id] = layer;
  }
}

function addEmployeeMarker(emp) {
  if (!trackingMap) return;
  var markerId = 'emp_' + emp.employee_id;
  if (employeeMarkers[markerId]) {
    employeeMarkers[markerId].setLatLng([emp.lat, emp.lng]);
    employeeMarkers[markerId].setIcon(createEmployeeIcon(true));
    return;
  }
  var marker = L.marker([emp.lat, emp.lng], {
    icon: createEmployeeIcon(true),
    zIndexOffset: 1000
  }).addTo(trackingMap);
  marker.bindPopup(
    '<div style="font-family:Cairo,sans-serif;min-width:220px">' +
    '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">' +
    '<span class="live-indicator online" style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#22c55e;box-shadow:0 0 6px rgba(34,197,94,0.6)"></span>' +
    '<span style="font-weight:700;font-size:14px">' + emp.employee_name + '</span>' +
    '</div>' +
    '<div style="font-size:12px;color:#8899b4;direction:ltr;text-align:right">' +
    '<div>📍 ' + emp.lat + ', ' + emp.lng + '</div>' +
    '<div>🎯 الدقة: ' + (emp.accuracy || '?') + 'م</div>' +
    (emp.battery ? '<div>🔋 البطارية: ' + emp.battery + '%</div>' : '') +
    '<div>📱 المصدر: ' + (emp.source || 'app') + '</div>' +
    '<div>🕐 ' + new Date(emp.created_at).toLocaleString('ar-SA') + '</div>' +
    '</div></div>'
  );
  employeeMarkers[markerId] = marker;
}

function removeOldMarkers(activeIds) {
  for (var key in employeeMarkers) {
    var empId = parseInt(key.replace('emp_', ''));
    if (activeIds.indexOf(empId) === -1) {
      trackingMap.removeLayer(employeeMarkers[key]);
      delete employeeMarkers[key];
    }
  }
}

function clearEmployeeMarkers() {
  for (var key in employeeMarkers) {
    if (trackingMap) trackingMap.removeLayer(employeeMarkers[key]);
  }
  employeeMarkers = {};
}

function focusEmployee(empId) {
  var marker = employeeMarkers['emp_' + empId];
  if (marker && trackingMap) {
    trackingMap.setView(marker.getLatLng(), 17, { animate: true });
    marker.openPopup();
  }
}

function focusZoneOnMap(zoneId) {
  var layer = zoneLayers[zoneId];
  if (layer && geofenceMap) {
    geofenceMap.fitBounds(layer.getBounds(), { padding: [30, 30], animate: true });
    layer.openPopup();
  }
}

function fitMapToAll() {
  if (!trackingMap) return;
  var allMarkers = Object.values(employeeMarkers);
  if (allMarkers.length > 0) {
    var group = L.featureGroup(allMarkers);
    trackingMap.fitBounds(group.getBounds(), { padding: [40, 40], animate: true });
  } else {
    trackingMap.setView([32.0755, 23.9752], 15);
  }
}

function fitZonesOnMap() {
  if (!geofenceMap) return;
  var allLayers = Object.values(zoneLayers);
  if (allLayers.length > 0) {
    var group = L.featureGroup(allLayers);
    geofenceMap.fitBounds(group.getBounds(), { padding: [30, 30], animate: true });
  } else {
    geofenceMap.setView([32.0755, 23.9752], 15);
  }
}

function toggleAutoCenter() {
  autoCenter = !autoCenter;
  var btn = document.getElementById('autoCenterBtn');
  if (autoCenter) {
    btn.classList.add('active');
    btn.innerHTML = '<i class="ti ti-crosshair"></i> تلقائي';
  } else {
    btn.classList.remove('active');
    btn.innerHTML = '<i class="ti ti-crosshair"></i> يدوي';
  }
}

function setDrawMode(mode, btn) {
  drawMode = mode;
  document.querySelectorAll('#drawTools .btn').forEach(function(b) { b.classList.remove('active'); });
  if (btn) btn.classList.add('active');
  if (geofenceMap) {
    if (currentDrawLayer) {
      geofenceMap.removeLayer(currentDrawLayer);
      currentDrawLayer = null;
    }
    if (mode === 'view') {
      geofenceMap.dragging.enable();
    } else {
      geofenceMap.dragging.disable();
    }
  }
}

function handleCircleDraw(latlng) {
  if (!geofenceMap) return;
  if (currentDrawLayer) geofenceMap.removeLayer(currentDrawLayer);
  currentDrawLayer = L.circle(latlng, {
    radius: 200,
    color: '#22c55e',
    fillColor: '#22c55e',
    fillOpacity: 0.15,
    weight: 2,
    dashArray: '5,5'
  }).addTo(geofenceMap);
  new L.marker(latlng, {
    icon: L.divIcon({
      className: 'draw-marker',
      html: '📍',
      iconSize: [20, 20],
      iconAnchor: [10, 10]
    })
  }).addTo(currentDrawLayer);
  document.getElementById('zoneCenterLat').value = latlng.lat.toFixed(6);
  document.getElementById('zoneCenterLng').value = latlng.lng.toFixed(6);
}

function handlePolygonDraw(latlng) {
  if (!geofenceMap) return;
  if (!window._polyPoints) window._polyPoints = [];
  window._polyPoints.push([latlng.lat, latlng.lng]);
  if (currentDrawLayer) geofenceMap.removeLayer(currentDrawLayer);
  if (window._polyPoints.length >= 2) {
    currentDrawLayer = L.polyline(window._polyPoints, {
      color: '#6366f1',
      weight: 2,
      dashArray: '5,5'
    }).addTo(geofenceMap);
  }
  L.circleMarker(latlng, {
    radius: 4,
    color: '#6366f1',
    fillColor: '#fff',
    fillOpacity: 1
  }).addTo(geofenceMap);
}

function handleRectangleDraw(latlng) {
  if (!geofenceMap) return;
  if (!window._rectStart) {
    window._rectStart = latlng;
    L.circleMarker(latlng, {
      radius: 4,
      color: '#f59e0b',
      fillColor: '#fff',
      fillOpacity: 1
    }).addTo(geofenceMap);
  } else {
    if (currentDrawLayer) geofenceMap.removeLayer(currentDrawLayer);
    var bounds = L.latLngBounds(window._rectStart, latlng);
    currentDrawLayer = L.rectangle(bounds, {
      color: '#f59e0b',
      fillColor: '#f59e0b',
      fillOpacity: 0.1,
      weight: 2,
      dashArray: '5,5'
    }).addTo(geofenceMap);
    window._rectStart = null;
  }
}

function clearDraw() {
  if (geofenceMap) {
    if (currentDrawLayer) {
      geofenceMap.removeLayer(currentDrawLayer);
      currentDrawLayer = null;
    }
    window._polyPoints = null;
    window._rectStart = null;
  }
}

function showOnMap(lat, lng) {
  if (trackingMap) {
    trackingMap.setView([lat, lng], 17, { animate: true });
    L.circleMarker([lat, lng], {
      radius: 6,
      color: '#ef4444',
      fillColor: '#ef4444',
      fillOpacity: 0.8
    }).addTo(trackingMap);
  }
}

function updateHeatmapMap(points) {
  if (!heatmapMap) return;
  if (window._heatPoints) {
    heatmapMap.removeLayer(window._heatPoints);
  }
  var maxVal = 1;
  var heatData = points.map(function(p) {
    if (p.weight > maxVal) maxVal = p.weight;
    return [p.lat, p.lng, p.weight || 1];
  });
  if (typeof L.heatLayer === 'function') {
    window._heatPoints = L.heatLayer(heatData, {
      radius: 25,
      blur: 15,
      maxZoom: 17,
      max: maxVal,
      gradient: {
        0.0: '#3b82f6',
        0.3: '#22c55e',
        0.5: '#f59e0b',
        0.7: '#ef4444',
        1.0: '#dc2626'
      }
    }).addTo(heatmapMap);
  } else {
    heatData.forEach(function(p) {
      L.circleMarker([p[0], p[1]], {
        radius: 6,
        color: '#ef4444',
        fillColor: '#ef4444',
        fillOpacity: 0.4
      }).addTo(heatmapMap);
    });
  }
}
