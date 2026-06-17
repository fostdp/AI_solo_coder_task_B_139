class RammedEarth3DViewer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container ${containerId} not found`);
            return;
        }

        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.wallSegments = [];
        this.erosionMeshes = [];
        this.windParticles = null;
        this.animationId = null;

        this.showErosion = true;
        this.showWindField = false;
        this.showWireframe = false;
        this.erosionIntensity = 0.5;
        this.currentSegmentId = 1;

        this.erosionColors = {
            low: new THREE.Color(0x1a9850),
            medium: new THREE.Color(0xfdae61),
            high: new THREE.Color(0xd73027)
        };

        this.init();
    }

    init() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;

        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x1a1a2e);
        this.scene.fog = new THREE.Fog(0x1a1a2e, 50, 200);

        this.camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
        this.camera.position.set(30, 20, 30);

        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.container.appendChild(this.renderer.domElement);

        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.minDistance = 5;
        this.controls.maxDistance = 100;
        this.controls.maxPolarAngle = Math.PI / 2;

        this.setupLighting();
        this.createGround();
        this.createAllWallSegments();
        this.createWindParticles();

        window.addEventListener('resize', () => this.onWindowResize());

        this.animate();
    }

    setupLighting() {
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
        this.scene.add(ambientLight);

        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(50, 50, 50);
        directionalLight.castShadow = true;
        directionalLight.shadow.mapSize.width = 2048;
        directionalLight.shadow.mapSize.height = 2048;
        directionalLight.shadow.camera.near = 0.5;
        directionalLight.shadow.camera.far = 200;
        directionalLight.shadow.camera.left = -50;
        directionalLight.shadow.camera.right = 50;
        directionalLight.shadow.camera.top = 50;
        directionalLight.shadow.camera.bottom = -50;
        this.scene.add(directionalLight);

        const hemisphereLight = new THREE.HemisphereLight(0x87ceeb, 0x362d1f, 0.3);
        this.scene.add(hemisphereLight);
    }

    createGround() {
        const groundGeometry = new THREE.PlaneGeometry(200, 200, 50, 50);
        const groundMaterial = new THREE.MeshStandardMaterial({
            color: 0x8b7355,
            roughness: 0.9,
            metalness: 0.1
        });

        const positions = groundGeometry.attributes.position;
        for (let i = 0; i < positions.count; i++) {
            const x = positions.getX(i);
            const y = positions.getY(i);
            const z = Math.sin(x * 0.1) * Math.cos(y * 0.1) * 0.2;
            positions.setZ(i, z);
        }
        groundGeometry.computeVertexNormals();

        const ground = new THREE.Mesh(groundGeometry, groundMaterial);
        ground.rotation.x = -Math.PI / 2;
        ground.receiveShadow = true;
        this.scene.add(ground);

        const gridHelper = new THREE.GridHelper(100, 50, 0x444444, 0x333333);
        gridHelper.position.y = 0.01;
        this.scene.add(gridHelper);
    }

    createAllWallSegments() {
        const segmentConfigs = [
            { id: 1, name: '西墙北段', x: -20, z: 0, length: 45, height: 3.2, thickness: 2.8, rotation: 0 },
            { id: 2, name: '西墙南段', x: -20, z: -20, length: 38, height: 2.5, thickness: 2.2, rotation: 0 },
            { id: 3, name: '北墙西段', x: -10, z: 25, length: 52, height: 3.5, thickness: 3.0, rotation: Math.PI / 2 },
            { id: 4, name: '北墙东段', x: 15, z: 25, length: 48, height: 3.8, thickness: 3.2, rotation: Math.PI / 2 },
            { id: 5, name: '东墙北段', x: 25, z: 0, length: 42, height: 2.8, thickness: 2.5, rotation: 0 },
            { id: 6, name: '东墙南段', x: 25, z: -18, length: 35, height: 2.2, thickness: 2.0, rotation: 0 },
            { id: 7, name: '南墙西段', x: -10, z: -25, length: 40, height: 3.0, thickness: 2.8, rotation: Math.PI / 2 },
            { id: 8, name: '南墙东段', x: 12, z: -25, length: 36, height: 2.6, thickness: 2.4, rotation: Math.PI / 2 }
        ];

        this.wallSegments = [];
        segmentConfigs.forEach(config => {
            const segmentGroup = this.createWallSegment(config);
            this.wallSegments.push({
                id: config.id,
                name: config.name,
                group: segmentGroup,
                config: config,
                erosionRate: 0.1 + Math.random() * 0.3
            });
            this.scene.add(segmentGroup);
        });
    }

    createWallSegment(config) {
        const group = new THREE.Group();

        const geometry = new THREE.BoxGeometry(config.length, config.height, config.thickness);

        const positions = geometry.attributes.position;
        const vertex = new THREE.Vector3();

        for (let i = 0; i < positions.count; i++) {
            vertex.fromBufferAttribute(positions, i);

            if (vertex.y > 0) {
                const noise = (Math.random() - 0.5) * 0.1;
                vertex.y += noise;
                vertex.x += (Math.random() - 0.5) * 0.05;
                vertex.z += (Math.random() - 0.5) * 0.05;
            }

            positions.setXYZ(i, vertex.x, vertex.y, vertex.z);
        }
        geometry.computeVertexNormals();

        const baseColor = new THREE.Color(0xc4a35a);
        const material = new THREE.MeshStandardMaterial({
            color: baseColor,
            roughness: 0.9,
            metalness: 0.0,
            flatShading: false,
            wireframe: this.showWireframe
        });

        const wallMesh = new THREE.Mesh(geometry, material);
        wallMesh.castShadow = true;
        wallMesh.receiveShadow = true;
        group.add(wallMesh);

        this.addSurfaceTexture(group, config);
        this.addLayerLines(group, config);
        this.createErosionOverlay(group, config);

        group.position.set(config.x, config.height / 2, config.z);
        group.rotation.y = config.rotation;

        group.userData = {
            segmentId: config.id,
            segmentName: config.name,
            wallMesh: wallMesh
        };

        return group;
    }

    addSurfaceTexture(group, config) {
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 256;
        const ctx = canvas.getContext('2d');

        const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
        gradient.addColorStop(0, '#d4b896');
        gradient.addColorStop(0.5, '#c4a35a');
        gradient.addColorStop(1, '#a08040');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        for (let i = 0; i < 500; i++) {
            const x = Math.random() * canvas.width;
            const y = Math.random() * canvas.height;
            const size = Math.random() * 3 + 1;
            const alpha = Math.random() * 0.3;

            ctx.fillStyle = `rgba(80, 60, 30, ${alpha})`;
            ctx.beginPath();
            ctx.arc(x, y, size, 0, Math.PI * 2);
            ctx.fill();
        }

        for (let y = 0; y < canvas.height; y += 20) {
            ctx.strokeStyle = `rgba(100, 80, 50, ${0.2 + Math.random() * 0.2})`;
            ctx.lineWidth = 1 + Math.random();
            ctx.beginPath();
            ctx.moveTo(0, y + Math.random() * 5);

            for (let x = 0; x < canvas.width; x += 10) {
                ctx.lineTo(x, y + Math.random() * 3);
            }
            ctx.stroke();
        }

        const texture = new THREE.CanvasTexture(canvas);
        texture.wrapS = THREE.RepeatWrapping;
        texture.wrapT = THREE.RepeatWrapping;
        texture.repeat.set(config.length / 10, config.height / 5);

        const material = new THREE.MeshStandardMaterial({
            map: texture,
            roughness: 0.9,
            metalness: 0.0,
            transparent: true,
            opacity: 0.9
        });

        const textureMesh = new THREE.Mesh(
            new THREE.BoxGeometry(config.length + 0.02, config.height + 0.02, config.thickness + 0.02),
            material
        );
        group.add(textureMesh);
    }

    addLayerLines(group, config) {
        const layerCount = Math.floor(config.height / 0.3);

        for (let i = 1; i < layerCount; i++) {
            const y = i * 0.3 - config.height / 2;

            const lineGeometry = new THREE.BufferGeometry();
            const points = [];

            for (let x = -config.length / 2; x <= config.length / 2; x += 0.5) {
                points.push(new THREE.Vector3(
                    x + (Math.random() - 0.5) * 0.1,
                    y + (Math.random() - 0.5) * 0.05,
                    config.thickness / 2 + 0.01
                ));
            }

            lineGeometry.setFromPoints(points);

            const lineMaterial = new THREE.LineBasicMaterial({
                color: 0x6b4423,
                transparent: true,
                opacity: 0.4
            });

            const line = new THREE.Line(lineGeometry, lineMaterial);
            group.add(line);

            const lineBack = line.clone();
            lineBack.position.z = -config.thickness / 2 - 0.02;
            group.add(lineBack);
        }
    }

    createErosionOverlay(group, config) {
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 256;
        const ctx = canvas.getContext('2d');

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        for (let i = 0; i < 50; i++) {
            const x = Math.random() * canvas.width;
            const y = canvas.height * (0.3 + Math.random() * 0.5);
            const width = 20 + Math.random() * 60;
            const height = 10 + Math.random() * 30;

            const gradient = ctx.createRadialGradient(x, y, 0, x, y, width);
            const intensity = Math.random();
            let color;

            if (intensity < 0.6) {
                color = `rgba(26, 152, 80, ${0.3 * intensity})`;
            } else if (intensity < 0.85) {
                color = `rgba(253, 174, 97, ${0.5 * intensity})`;
            } else {
                color = `rgba(215, 48, 39, ${0.7 * intensity})`;
            }

            gradient.addColorStop(0, color);
            gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');

            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.ellipse(x, y, width, height, Math.random() * Math.PI, 0, Math.PI * 2);
            ctx.fill();
        }

        const texture = new THREE.CanvasTexture(canvas);
        texture.wrapS = THREE.RepeatWrapping;
        texture.wrapT = THREE.RepeatWrapping;

        const material = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            opacity: 0.7 * this.erosionIntensity,
            depthWrite: false
        });

        const erosionMesh = new THREE.Mesh(
            new THREE.BoxGeometry(config.length + 0.05, config.height + 0.05, config.thickness + 0.05),
            material
        );

        erosionMesh.visible = this.showErosion;
        group.add(erosionMesh);

        group.userData.erosionMesh = erosionMesh;
        this.erosionMeshes.push(erosionMesh);
    }

    createWindParticles() {
        const particleCount = 500;
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(particleCount * 3);
        const velocities = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);

        const bounds = { minX: -50, maxX: 50, minY: 0, maxY: 10, minZ: -50, maxZ: 50 };

        for (let i = 0; i < particleCount; i++) {
            positions[i * 3] = bounds.minX + Math.random() * (bounds.maxX - bounds.minX);
            positions[i * 3 + 1] = bounds.minY + Math.random() * (bounds.maxY - bounds.minY);
            positions[i * 3 + 2] = bounds.minZ + Math.random() * (bounds.maxZ - bounds.minZ);

            velocities[i * 3] = (Math.random() - 0.5) * 0.1;
            velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.05;
            velocities[i * 3 + 2] = -0.1 - Math.random() * 0.1;

            const color = new THREE.Color();
            color.setHSL(0.5 + Math.random() * 0.2, 0.8, 0.6);
            colors[i * 3] = color.r;
            colors[i * 3 + 1] = color.g;
            colors[i * 3 + 2] = color.b;
        }

        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

        const material = new THREE.PointsMaterial({
            size: 0.2,
            vertexColors: true,
            transparent: true,
            opacity: 0.8,
            blending: THREE.AdditiveBlending,
            sizeAttenuation: true
        });

        this.windParticles = new THREE.Points(geometry, material);
        this.windParticles.visible = this.showWindField;
        this.windParticles.userData = {
            velocities: velocities,
            bounds: bounds,
            windSpeed: 0.05,
            windDirection: 0
        };

        this.scene.add(this.windParticles);
    }

    updateWindParticles() {
        if (!this.windParticles || !this.showWindField) return;

        const positions = this.windParticles.geometry.attributes.position.array;
        const velocities = this.windParticles.userData.velocities;
        const bounds = this.windParticles.userData.bounds;
        const windSpeed = this.windParticles.userData.windSpeed;
        const windDirection = this.windParticles.userData.windDirection;

        const windX = Math.sin(windDirection) * windSpeed;
        const windZ = Math.cos(windDirection) * windSpeed;

        for (let i = 0; i < positions.length / 3; i++) {
            positions[i * 3] += velocities[i * 3] + windX;
            positions[i * 3 + 1] += velocities[i * 3 + 1];
            positions[i * 3 + 2] += velocities[i * 3 + 2] + windZ;

            if (positions[i * 3] > bounds.maxX) positions[i * 3] = bounds.minX;
            if (positions[i * 3] < bounds.minX) positions[i * 3] = bounds.maxX;
            if (positions[i * 3 + 1] > bounds.maxY) positions[i * 3 + 1] = bounds.minY;
            if (positions[i * 3 + 1] < bounds.minY) positions[i * 3 + 1] = bounds.maxY;
            if (positions[i * 3 + 2] > bounds.maxZ) positions[i * 3 + 2] = bounds.minZ;
            if (positions[i * 3 + 2] < bounds.minZ) positions[i * 3 + 2] = bounds.maxZ;
        }

        this.windParticles.geometry.attributes.position.needsUpdate = true;
    }

    updateErosionColors(segmentId, erosionRate) {
        const segment = this.wallSegments.find(s => s.id === segmentId);
        if (!segment) return;

        segment.erosionRate = erosionRate;

        const erosionMesh = segment.group.userData.erosionMesh;
        if (erosionMesh) {
            let color;
            if (erosionRate < 0.2) {
                color = this.erosionColors.low;
            } else if (erosionRate < 0.5) {
                color = this.erosionColors.medium;
            } else {
                color = this.erosionColors.high;
            }

            const intensity = Math.min(erosionRate / 0.5, 1.0);
            erosionMesh.material.color = color;
            erosionMesh.material.opacity = 0.3 + intensity * 0.5 * this.erosionIntensity;
        }

        if (segmentId === this.currentSegmentId) {
            this.highlightSegment(segmentId);
        }
    }

    highlightSegment(segmentId) {
        this.currentSegmentId = segmentId;

        this.wallSegments.forEach(segment => {
            const wallMesh = segment.group.userData.wallMesh;
            if (wallMesh) {
                if (segment.id === segmentId) {
                    wallMesh.material.emissive = new THREE.Color(0x667eea);
                    wallMesh.material.emissiveIntensity = 0.3;
                } else {
                    wallMesh.material.emissive = new THREE.Color(0x000000);
                    wallMesh.material.emissiveIntensity = 0;
                }
            }
        });

        const segment = this.wallSegments.find(s => s.id === segmentId);
        if (segment) {
            const targetPos = segment.group.position.clone();
            targetPos.x += 20;
            targetPos.y += 15;
            targetPos.z += 20;

            this.camera.position.lerp(targetPos, 0.1);
            this.controls.target.lerp(segment.group.position, 0.1);
        }
    }

    setShowErosion(show) {
        this.showErosion = show;
        this.erosionMeshes.forEach(mesh => {
            mesh.visible = show;
        });
    }

    setShowWindField(show) {
        this.showWindField = show;
        if (this.windParticles) {
            this.windParticles.visible = show;
        }
    }

    setShowWireframe(show) {
        this.showWireframe = show;
        this.wallSegments.forEach(segment => {
            const wallMesh = segment.group.userData.wallMesh;
            if (wallMesh) {
                wallMesh.material.wireframe = show;
            }
        });
    }

    setErosionIntensity(intensity) {
        this.erosionIntensity = intensity / 100;
        this.erosionMeshes.forEach(mesh => {
            mesh.material.opacity = 0.3 + mesh.material.opacity * 0.7 * this.erosionIntensity;
        });
    }

    setWindParameters(speed, direction) {
        if (this.windParticles) {
            this.windParticles.userData.windSpeed = speed * 0.01;
            this.windParticles.userData.windDirection = direction * Math.PI / 180;
        }
    }

    onWindowResize() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;

        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();

        this.renderer.setSize(width, height);
    }

    animate() {
        this.animationId = requestAnimationFrame(() => this.animate());

        this.controls.update();
        this.updateWindParticles();

        this.wallSegments.forEach(segment => {
            segment.group.rotation.y = segment.config.rotation +
                Math.sin(Date.now() * 0.0001 + segment.id) * 0.001;
        });

        this.renderer.render(this.scene, this.camera);
    }

    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }

        if (this.renderer) {
            this.renderer.dispose();
            if (this.renderer.domElement && this.renderer.domElement.parentNode) {
                this.renderer.domElement.parentNode.removeChild(this.renderer.domElement);
            }
        }

        this.scene?.traverse(object => {
            if (object.geometry) object.geometry.dispose();
            if (object.material) {
                if (Array.isArray(object.material)) {
                    object.material.forEach(m => m.dispose());
                } else {
                    object.material.dispose();
                }
            }
        });

        this.wallSegments = [];
        this.erosionMeshes = [];
        this.windParticles = null;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
    }
}

window.RammedEarth3DViewer = RammedEarth3DViewer;
